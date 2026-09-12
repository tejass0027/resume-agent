"""FastAPI backend for the AI Resume Screener.

Serves the static frontend and exposes /api/screen, which streams
newline-delimited JSON progress events while screening a batch of
resumes against a job description.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from docx_utils import extract_text_from_docx
from pdf_utils import extract_text_from_pdf
from providers import PROVIDERS

MAX_RESUMES = 1000
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AI Resume Screener")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/providers")
async def list_providers() -> dict:
    return {
        name: {
            "default_model": provider.module.DEFAULT_MODEL,
            "key_label": provider.key_label,
            "key_help": provider.key_help,
        }
        for name, provider in PROVIDERS.items()
    }


def _extract_resume_text(filename: str, file_bytes: bytes) -> tuple[str, Optional[str]]:
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension == "pdf":
        return extract_text_from_pdf(file_bytes, filename)
    if extension == "docx":
        return extract_text_from_docx(file_bytes, filename)
    return "", f"Unsupported file type: .{extension}"


def _event(payload: dict) -> bytes:
    return (json.dumps(payload) + "\n").encode()


async def _screen_stream(
    provider_name: str,
    api_key: str,
    model: str,
    job_description: str,
    max_concurrency: int,
    max_retries: int,
    files: list[UploadFile],
) -> AsyncIterator[bytes]:
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        yield _event({"type": "error", "message": f"Unknown provider: {provider_name}"})
        return

    if len(files) > MAX_RESUMES:
        yield _event({"type": "error", "message": f"Please upload at most {MAX_RESUMES} resumes at a time."})
        return

    resumes: list[tuple[str, str]] = []
    for f in files:
        content = await f.read()
        text, err = _extract_resume_text(f.filename, content)
        if err:
            yield _event({"type": "extraction_error", "filename": f.filename, "message": err})
        else:
            resumes.append((f.filename, text))

    if not resumes:
        yield _event({"type": "error", "message": "No resumes could be read. Please check the uploaded files."})
        return

    queue: asyncio.Queue = asyncio.Queue()

    def on_progress(done: int, total: int) -> None:
        queue.put_nowait({"type": "progress", "done": done, "total": total})

    async def run() -> None:
        try:
            results = await provider.module.run_batch(
                api_key=api_key,
                job_description=job_description,
                resumes=resumes,
                model=model,
                max_concurrency=max_concurrency,
                max_retries=max_retries,
                progress_callback=on_progress,
            )
            await queue.put({"type": "done", "results": results})
        except Exception as exc:
            await queue.put({"type": "error", "message": str(exc)})

    task = asyncio.create_task(run())
    try:
        while True:
            item = await queue.get()
            yield _event(item)
            if item["type"] in ("done", "error"):
                break
    finally:
        await task


@app.post("/api/screen")
async def screen(
    provider: str = Form(...),
    api_key: str = Form(...),
    model: str = Form(...),
    job_description: str = Form(...),
    max_concurrency: int = Form(5),
    max_retries: int = Form(5),
    files: list[UploadFile] = File(...),
) -> StreamingResponse:
    return StreamingResponse(
        _screen_stream(provider, api_key, model, job_description, max_concurrency, max_retries, files),
        media_type="application/x-ndjson",
    )
