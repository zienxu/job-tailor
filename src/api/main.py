"""FastAPI app. Run: .venv/bin/uvicorn src.api.main:app --env-file .env"""
import json
import sqlite3
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, StringConstraints

from src.api import db
from src.api.tailor import tailor

app = FastAPI(title="job-tailor")

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


class Item(BaseModel):
    role_id: int
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
        _write(conn, f"UPDATE {table} SET {', '.join(c + ' = ?' for c in cols)} WHERE id = ?",
               [getattr(body, c) for c in cols] + [id])
        return _get(conn, table, id)

    @app.delete(f"/{table}/{{id}}", status_code=204)
    def delete(id: int, conn=Depends(get_conn)):
        _get(conn, table, id)
        _write(conn, f"DELETE FROM {table} WHERE id = ?", (id,))


_crud("roles", Role)
_crud("bullets", Item)
_crud("stories", Item)


@app.post("/jobs", status_code=201)
def create_job(body: Job, conn=Depends(get_conn)):
    cur = _write(conn, "INSERT INTO jobs (text, company, title, link) VALUES (?, ?, ?, ?)",
                 (body.text, body.company, body.title, body.link))
    return _get(conn, "jobs", cur.lastrowid)


@app.get("/jobs/{id}")
def get_job(id: int, conn=Depends(get_conn)):
    return _get(conn, "jobs", id)


@app.post("/jobs/{id}/tailor")
def tailor_job(id: int, conn=Depends(get_conn)):
    job = _get(conn, "jobs", id)
    try:
        return tailor(job["text"], db.load_profile(conn))
    except Exception as e:  # LLM call failed; never echo prompt or profile
        raise HTTPException(502, f"LLM call failed: {type(e).__name__}")


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
