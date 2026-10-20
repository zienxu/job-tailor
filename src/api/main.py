"""FastAPI app. Run: .venv/bin/uvicorn src.api.main:app --env-file .env"""
import json
import sqlite3
from typing import Annotated, Literal
from urllib.error import HTTPError

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints

from src.api import ats, db, pdf
from src.api.critic import critique
from src.api.factcheck import check_bullet
from src.api.fetch_job import REFUSED, fetch_job
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
    kind: Literal["experience", "project", "education"] = "experience"


class Item(BaseModel):
    role_id: int
    text: NonBlank


class Entry(BaseModel):
    section: Literal["leadership", "skills"]
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


def _crud(table: str, Model: type[BaseModel]) -> None:
    cols = list(Model.model_fields)

    @app.post(f"/{table}", status_code=201)
    def create(body: Model, conn=Depends(get_conn)):
        cur = _write(conn, f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     [getattr(body, c) for c in cols])
        return _get(conn, table, cur.lastrowid)

    @app.get(f"/{table}")
    def list_all(conn=Depends(get_conn)):
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]

    @app.get(f"/{table}/{{id}}")
    def get_one(id: int, conn=Depends(get_conn)):
        return _get(conn, table, id)

    @app.put(f"/{table}/{{id}}")
    def update(id: int, body: Model, conn=Depends(get_conn)):
        _get(conn, table, id)
        # Only fields sent are written, so e.g. a PUT without kind can't turn a project into experience.
        fields = body.model_dump(exclude_unset=True)
        _write(conn, f"UPDATE {table} SET {', '.join(c + ' = ?' for c in fields)} WHERE id = ?",
               [*fields.values(), id])
        return _get(conn, table, id)

    @app.delete(f"/{table}/{{id}}", status_code=204)
    def delete(id: int, conn=Depends(get_conn)):
        _get(conn, table, id)
        _write(conn, f"DELETE FROM {table} WHERE id = ?", (id,))


_crud("roles", Role)
_crud("bullets", Item)
_crud("stories", Item)
_crud("entries", Entry)


@app.post("/jobs", status_code=201)
def create_job(body: Job, conn=Depends(get_conn)):
    cur = _write(conn, "INSERT INTO jobs (text, company, title, link) VALUES (?, ?, ?, ?)",
                 (body.text, body.company, body.title, body.link))
    return _get(conn, "jobs", cur.lastrowid)


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
    return _get(conn, "jobs", id)


@app.post("/jobs/{id}/tailor")
def tailor_job(id: int, conn=Depends(get_conn)):
    job = _get(conn, "jobs", id)
    profile = db.load_profile(conn)
    try:
        result = tailor(job["text"], profile)
    except Exception as e:  # LLM call failed; never echo prompt or profile
        raise HTTPException(502, f"LLM call failed: {type(e).__name__}")
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


@app.post("/jobs/{id}/check")
def check_draft(id: int, body: CheckReq, conn=Depends(get_conn)):
    job = _get(conn, "jobs", id)
    sources = _sources(db.load_profile(conn))
    return {"ats": ats.score(job["text"], body.text),
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
    leadership: list[LabelEntry] = []
    projects: list[ProjectEntry] = []
    skills: list[LabelEntry] = []
    order: list[Literal["summary", "education", "experience", "leadership", "projects", "skills"]] = pdf.ORDER


class Render(BaseModel):
    resume: Resume


@app.post("/preview", response_class=HTMLResponse)
def preview(body: Render):
    return pdf.render_html(body.resume.model_dump(), base=PREVIEW_BASE)


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
