"""FastAPI app. Run: .venv/bin/uvicorn src.api.main:app --env-file .env"""
import json
import sqlite3
from typing import Annotated, Literal
from urllib.error import HTTPError

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints, ValidationError

from src.api import ats, db, pdf
from src.api.critic import critique
from src.api.factcheck import check_bullet
from src.api.fetch_job import REFUSED, fetch_job
from src.api.fit import grade
from src.api.tailor import _sources, tailor

app = FastAPI(title="job-tailor")
# CSS and fonts for the editor preview; the Vite proxy serves this under /api.
app.mount("/templates", StaticFiles(directory=pdf.TEMPLATES), name="templates")
PREVIEW_BASE = "/api/templates/"


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, exc: RequestValidationError):
    # FastAPI's default 422 echoes the request body (resume, contacts) back into the UI's error alert.
    return JSONResponse({"detail": [{k: e[k] for k in ("loc", "msg", "type")} for e in exc.errors()]}, 422)

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


class Role(BaseModel):
    company: str
    title: str
    start_date: str = ""
    end_date: str = ""
    kind: Literal["experience", "project", "education", "leadership"] = "experience"


class Item(BaseModel):
    role_id: int
    text: NonBlank


class Bullet(Item):
    position: int = None  # omitted -> a DB trigger sets it to the id; an explicit null is rejected


class Entry(BaseModel):
    section: Literal["skills", "eligibility"]  # leadership moved to roles in step 7c2b; eligibility is grade-only
    label: NonBlank
    text: NonBlank


class Job(BaseModel):
    text: NonBlank
    company: str = ""
    title: str = ""
    link: str = ""


class Version(BaseModel):
    content: dict


def _get(conn, table: str, id: int) -> dict:
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"{table} {id} not found")
    return dict(row)


def _write(conn, sql: str, params) -> sqlite3.Cursor:
    try:
        cur = conn.execute(sql, params)
    except sqlite3.IntegrityError as e:  # e.g. unknown role_id / job_id
        raise HTTPException(422, str(e))
    conn.commit()
    return cur


# Rows only swap within their own list: same role kind, same bullet role, same entry section.
GROUP = {"roles": "kind", "bullets": "role_id", "entries": "section"}


def _crud(table: str, Model: type[BaseModel]) -> None:
    cols = list(Model.model_fields)
    order = "position, id" if table in db.ORDERED else "id"

    @app.post(f"/{table}", status_code=201)
    def create(body: Model, conn=Depends(get_conn)):
        cur = _write(conn, f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     [getattr(body, c) for c in cols])
        return _get(conn, table, cur.lastrowid)

    @app.get(f"/{table}")
    def list_all(conn=Depends(get_conn)):
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY {order}")]

    @app.get(f"/{table}/{{id}}")
    def get_one(id: int, conn=Depends(get_conn)):
        return _get(conn, table, id)

    @app.put(f"/{table}/{{id}}")
    def update(id: int, body: Model, conn=Depends(get_conn)):
        row = _get(conn, table, id)
        # Only fields sent are written, so e.g. a PUT without kind can't turn a project into experience.
        fields = body.model_dump(exclude_unset=True)
        # A grade-only eligibility fact must never become a skills entry that prints on the resume.
        if table == "entries" and fields.get("section", row["section"]) != row["section"]:
            raise HTTPException(422, "an entry can't change section")
        _write(conn, f"UPDATE {table} SET {', '.join(c + ' = ?' for c in fields)} WHERE id = ?",
               [*fields.values(), id])
        return _get(conn, table, id)

    @app.delete(f"/{table}/{{id}}", status_code=204)
    def delete(id: int, conn=Depends(get_conn)):
        _get(conn, table, id)
        _write(conn, f"DELETE FROM {table} WHERE id = ?", (id,))

    if table not in db.ORDERED:
        return

    @app.post(f"/{table}/{{a}}/swap/{{b}}", status_code=204)
    def swap(a: int, b: int, conn=Depends(get_conn)):
        conn.execute("BEGIN IMMEDIATE")  # take the write lock before reading, so overlapping swaps can't both read old positions
        ra, rb = _get(conn, table, a), _get(conn, table, b)
        if ra[GROUP[table]] != rb[GROUP[table]]:
            raise HTTPException(422, f"{table} {a} and {b} are in different {GROUP[table]}s")
        conn.execute(f"UPDATE {table} SET position = ? WHERE id = ?", (rb["position"], a))
        conn.execute(f"UPDATE {table} SET position = ? WHERE id = ?", (ra["position"], b))
        conn.commit()  # one commit: both positions change or neither


_crud("roles", Role)
_crud("bullets", Bullet)
_crud("stories", Item)
_crud("entries", Entry)


def _job(row) -> dict:
    """A job as the API returns it: the stored grade JSON decoded, None when ungraded."""
    job = dict(row)
    return {**job, "grade": json.loads(job["grade"]) if job["grade"] else None}


@app.post("/jobs", status_code=201)
def create_job(body: Job, conn=Depends(get_conn)):
    cur = _write(conn, "INSERT INTO jobs (text, company, title, link) VALUES (?, ?, ?, ?)",
                 (body.text, body.company, body.title, body.link))
    return _job(_get(conn, "jobs", cur.lastrowid))


class FetchReq(BaseModel):
    url: NonBlank


@app.post("/jobs/fetch")
def fetch_job_link(body: FetchReq):
    try:
        return fetch_job(body.url)
    except ValueError:
        raise HTTPException(422, REFUSED)
    except HTTPError as e:
        if e.code == 404:
            raise HTTPException(404, "job not found")
        raise HTTPException(502, f"fetch failed: HTTP {e.code}")
    except Exception as e:  # upstream down, 404, bad JSON
        raise HTTPException(502, f"fetch failed: {type(e).__name__}")


@app.get("/jobs/{id}")
def get_job(id: int, conn=Depends(get_conn)):
    return _job(_get(conn, "jobs", id))


@app.post("/jobs/{id}/grade")
def grade_job(id: int, conn=Depends(get_conn)):
    job = _get(conn, "jobs", id)
    profile = db.load_profile(conn, full=True)
    try:
        result = grade(job["text"], profile)
    except Exception as e:  # LLM call failed or bad response; store nothing, never echo prompt or profile
        raise HTTPException(502, f"grade failed: {type(e).__name__}")
    # The card shows the cited saved text; a snapshot at grade time, refreshed by re-grading.
    text_of = {r["id"]: f"{r['company']}, {r['title']}" for r in profile["roles"]}
    text_of |= {x["id"]: x["text"] for x in profile["bullets"] + profile["stories"]}
    text_of |= {s["id"]: f"{s['label']}: {s['text']}" for s in profile["skills"] + profile["facts"]}
    for r in result["requirements"]:
        r["evidence"] = [text_of[i] for i in r["evidence_ids"]]
    _write(conn, "UPDATE jobs SET grade = ? WHERE id = ?", (json.dumps(result), id))
    return result


@app.post("/jobs/{id}/tailor")
def tailor_job(id: int, conn=Depends(get_conn)):
    job = _get(conn, "jobs", id)
    profile = db.load_profile(conn)
    try:
        result = tailor(job["text"], profile)
    except Exception as e:  # LLM call failed; never echo prompt or profile
        raise HTTPException(502, f"LLM call failed: {type(e).__name__}")
    # This job now owns the editor; drop other runs never saved to the tracker so they don't pile up.
    # Done here, not in POST /jobs, so grading a new job never deletes the draft being edited.
    _write(conn, "DELETE FROM jobs WHERE id != ? AND NOT EXISTS"
                 " (SELECT 1 FROM resume_versions v WHERE v.job_id = jobs.id)", (id,))
    # The editor groups bullets under the role their cited source belongs to.
    role_of = {s["id"]: s["role_id"] for s in profile["bullets"] + profile["stories"]}
    for b in result["bullets"]:
        sid = b["source_id"]
        b["role_id"] = role_of.get(sid) if isinstance(sid, str) else None
    return result


class CitedBullet(BaseModel):
    text: str
    source_id: str | None = None


class CheckReq(BaseModel):
    text: str
    bullets: list[CitedBullet]
    roles: dict[str, str] = Field({}, max_length=500)  # role key -> that role's included text, for per-role hit counts


@app.post("/jobs/{id}/check")
def check_draft(id: int, body: CheckReq, conn=Depends(get_conn)):
    job = _get(conn, "jobs", id)
    sources = _sources(db.load_profile(conn))
    terms = ats.extract_terms(job["text"])
    return {"ats": ats.score(job["text"], body.text),
            "role_hits": {k: ats.hits(terms, text) for k, text in body.roles.items()},
            "flags": [check_bullet(b.text, b.source_id, sources) for b in body.bullets]}


class CritiqueReq(BaseModel):
    bullets: list[CitedBullet]


@app.post("/jobs/{id}/critique")
def critique_draft(id: int, body: CritiqueReq, conn=Depends(get_conn)):
    job = _get(conn, "jobs", id)
    return critique(job["text"], {"bullets": [{"text": b.text} for b in body.bullets]})


class ExperienceEntry(BaseModel):
    company: str
    title: str
    dates: str = ""
    bullets: list[str]


class ProjectEntry(BaseModel):
    name: str
    role: str
    dates: str = ""
    bullets: list[str]


class EducationEntry(BaseModel):
    school: str
    degree: str
    date: str = ""
    details: list[str] = []


class LabelEntry(BaseModel):
    label: str
    text: str


class Resume(BaseModel):
    name: str = ""
    contacts: list[str] = []
    summary: str = ""
    education: list[EducationEntry] = []
    experience: list[ExperienceEntry] = []
    leadership: list[ProjectEntry] = []
    projects: list[ProjectEntry] = []
    skills: list[LabelEntry] = []
    order: list[Literal["summary", "education", "experience", "leadership", "projects", "skills"]] = pdf.ORDER


class Render(BaseModel):
    resume: Resume
    job_id: int | None = None
    fallback: list[str] = Field([], max_length=500)  # texts of included fallback bullets, for the removal order


@app.post("/preview")
def preview(body: Render, conn=Depends(get_conn)):  # plain def: render_pdf uses sync Playwright
    resume = body.resume.model_dump()
    terms = ats.extract_terms(_get(conn, "jobs", body.job_id)["text"]) if body.job_id is not None else []
    fit = pdf.page_fit(resume, pdf.render_pdf(resume), set(body.fallback), terms)
    return {"html": pdf.render_html(resume, base=PREVIEW_BASE), **fit}


@app.post("/pdf")
def download_pdf(body: Render):  # plain def: render_pdf uses sync Playwright
    return Response(pdf.render_pdf(body.resume.model_dump()), media_type="application/pdf")


def _version(row) -> dict:
    return {**dict(row), "content": json.loads(row["content"])}


@app.post("/jobs/{id}/versions", status_code=201)
def save_version(id: int, body: Version, conn=Depends(get_conn)):
    _get(conn, "jobs", id)
    cur = _write(conn, "INSERT INTO resume_versions (job_id, content) VALUES (?, ?)",
                 (id, json.dumps(body.content)))
    return _version(conn.execute("SELECT * FROM resume_versions WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.get("/jobs/{id}/versions")
def list_versions(id: int, conn=Depends(get_conn)):
    _get(conn, "jobs", id)
    return [_version(r) for r in conn.execute(
        "SELECT * FROM resume_versions WHERE job_id = ? ORDER BY id", (id,))]


@app.get("/versions/latest")
def latest_version(conn=Depends(get_conn)):
    row = conn.execute("SELECT * FROM resume_versions ORDER BY id DESC LIMIT 1").fetchone()
    return _version(row) if row else None


@app.get("/versions/{id}/pdf")
def version_pdf(id: int, conn=Depends(get_conn)):  # plain def: render_pdf uses sync Playwright
    content = json.loads(_get(conn, "resume_versions", id)["content"])
    if "resume" not in content:  # versions saved before step 8 stored only the draft
        raise HTTPException(409, "saved before the tracker, can't rebuild")
    try:  # stored JSON was never validated on save
        resume = Resume.model_validate(content["resume"]).model_dump()
    except ValidationError:
        raise HTTPException(409, "stored resume is invalid, can't rebuild")
    return Response(pdf.render_pdf(resume), media_type="application/pdf")


@app.get("/jobs")
def list_jobs(conn=Depends(get_conn)):
    versions = {}
    for v in conn.execute("SELECT id, job_id, created_at FROM resume_versions ORDER BY id"):
        versions.setdefault(v["job_id"], []).append({"id": v["id"], "created_at": v["created_at"]})
    return [{**_job(j), "versions": versions.get(j["id"], [])}
            # Only jobs saved with "Save in tracker"; Tailor also makes a job row, for /check and /preview.
            for j in conn.execute("SELECT * FROM jobs WHERE EXISTS"
                                  " (SELECT 1 FROM resume_versions v WHERE v.job_id = jobs.id) ORDER BY id DESC")]


class JobUpdate(BaseModel):
    company: str = ""
    title: str = ""
    link: str = ""
    status: Literal["saved", "applied", "interview", "offer", "rejected"] = "saved"
    applied_at: Annotated[str, StringConstraints(pattern=r"^(\d{4}-\d{2}-\d{2})?$")] = ""  # <input type="date"> value
    notes: str = ""
    version_id: int | None = None


@app.put("/jobs/{id}")
def update_job(id: int, body: JobUpdate, conn=Depends(get_conn)):
    job = {**_get(conn, "jobs", id), **body.model_dump(exclude_unset=True)}
    vid = job["version_id"]
    if vid is not None and not conn.execute(
            "SELECT 1 FROM resume_versions WHERE id = ? AND job_id = ?", (vid, id)).fetchone():
        raise HTTPException(422, f"version {vid} is not a version of job {id}")
    if job["status"] == "applied" and vid is None:
        raise HTTPException(422, "marking applied needs the version sent")
    fields = body.model_dump(exclude_unset=True)
    if fields:
        _write(conn, f"UPDATE jobs SET {', '.join(c + ' = ?' for c in fields)} WHERE id = ?", [*fields.values(), id])
    return _job(_get(conn, "jobs", id))


@app.delete("/jobs/{id}", status_code=204)
def delete_job(id: int, conn=Depends(get_conn)):
    _get(conn, "jobs", id)
    _write(conn, "DELETE FROM jobs WHERE id = ?", (id,))  # versions cascade
