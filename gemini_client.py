"""Async Gemini client for batch resume screening against a job description.

Handles prompt construction (tag-based, per best practices), forces strict
structured JSON output via a response schema, and manages concurrency +
rate limit backoff for large batches.
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import Callable, Optional

from google import genai
from google.genai import errors, types

DEFAULT_MODEL = "gemini-3.6-flash"
MAX_OUTPUT_TOKENS = 8192
DEFAULT_MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 60.0

SYSTEM_PROMPT = """\
You are an uncompromising, highly accurate AI Resume Auditor. Your sole purpose is to map a \
candidate resume to a job description's requirements with 100% objective accuracy. You do not \
infer, guess, or give the benefit of the doubt.

Zero-Tolerance Rules:
- No Hallucinations: only credit a requirement as met if there is explicit, written proof in the resume.
- No Assumptions: if a requirement specifies a duration (e.g. "5 years of Python") and the resume \
only says "Python" with no duration, treat the duration as unmet. Do not infer skills from job \
titles (e.g. do not assume "Software Engineer" implies knowledge of any specific language or tool \
unless it is explicitly written).
- Exact Evidence: for every Must-Have and Nice-to-Have requirement, include a short verbatim quote \
from the resume as evidence, or the literal string "NO EVIDENCE FOUND" if the resume does not \
support it.
- Strict Scoring: match_score must reflect the proportion of Must-Have requirements actually met \
(with evidence). A resume missing one or more Must-Haves cannot score above 50 and its status must \
be "Rejected". A resume meeting all Must-Haves but with weak Nice-to-Have coverage should be \
"Flagged". A resume meeting all Must-Haves and most Nice-to-Haves should be "Shortlisted".

You will be given a <job_description> and a <resume>. First, mentally separate the job \
description's requirements into Must-Haves (required, mandatory) and Nice-to-Haves (preferred, \
bonus) - use explicit labels in the JD if present, otherwise use language cues ("required", \
"must", "minimum" vs. "preferred", "plus", "nice to have"). Then scan the resume for explicit \
evidence of each requirement, including years of relevant experience.

Respond with ONLY a single JSON object matching the required schema. Do not include markdown \
fences, commentary, or any text outside the JSON object.
"""

RESUME_EVAL_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate_name": {
            "type": "string",
            "description": (
                "The candidate's full name as it appears on the resume. Use 'Unknown' only "
                "if no name is found anywhere in the text."
            ),
        },
        "match_score": {
            "type": "integer",
            "description": "Overall match score from 0-100, per the Zero-Tolerance scoring rules.",
            "minimum": 0,
            "maximum": 100,
        },
        "years_experience_estimated": {
            "type": "number",
            "description": (
                "Total years of relevant professional experience, estimated only from "
                "explicit dates/durations stated in the resume."
            ),
        },
        "must_haves_met": {
            "type": "array",
            "description": "One entry per Must-Have requirement identified in the job description.",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "met": {"type": "boolean"},
                    "evidence": {
                        "type": "string",
                        "description": "Verbatim quote from the resume, or 'NO EVIDENCE FOUND'.",
                    },
                },
                "required": ["requirement", "met", "evidence"],
            },
        },
        "nice_to_haves_met": {
            "type": "array",
            "description": "One entry per Nice-to-Have requirement identified in the job description.",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "met": {"type": "boolean"},
                    "evidence": {
                        "type": "string",
                        "description": "Verbatim quote from the resume, or 'NO EVIDENCE FOUND'.",
                    },
                },
                "required": ["requirement", "met", "evidence"],
            },
        },
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short bullet points on the candidate's strongest, evidence-backed qualifications.",
        },
        "weaknesses": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short bullet points on missing Must-Haves, gaps, or concerns.",
        },
        "status": {
            "type": "string",
            "enum": ["Shortlisted", "Flagged", "Rejected"],
            "description": (
                "Shortlisted = all Must-Haves met and strong Nice-to-Have coverage. "
                "Flagged = all Must-Haves met but weak Nice-to-Have coverage or ambiguity. "
                "Rejected = at least one Must-Have is not met."
            ),
        },
    },
    "required": ["candidate_name", "match_score", "strengths", "weaknesses", "status"],
}


def _build_user_prompt(job_description: str, resume_text: str, filename: str) -> str:
    return (
        f'<job_description>\n{job_description.strip()}\n</job_description>\n\n'
        f'<resume filename="{filename}">\n{resume_text.strip()}\n</resume>\n\n'
        "Evaluate this resume against the job description above and return the JSON evaluation."
    )


def _error_result(filename: str, message: str) -> dict:
    return {
        "filename": filename,
        "candidate_name": filename,
        "match_score": 0,
        "years_experience_estimated": None,
        "must_haves_met": [],
        "nice_to_haves_met": [],
        "strengths": [],
        "weaknesses": [f"Screening error: {message}"],
        "status": "Error",
    }


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, errors.APIError):
        return exc.code == 429 or exc.code >= 500
    return False


async def evaluate_resume(
    client: genai.Client,
    semaphore: asyncio.Semaphore,
    filename: str,
    resume_text: str,
    job_description: str,
    model: str = DEFAULT_MODEL,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict:
    """Evaluate a single resume against the job description, with rate-limit backoff."""
    attempt = 0
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=RESUME_EVAL_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    async with semaphore:
        while True:
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=_build_user_prompt(job_description, resume_text, filename),
                    config=config,
                )
                if not response.text:
                    return _error_result(filename, "Model returned an empty response.")
                result = json.loads(response.text)
                result["filename"] = filename
                result.setdefault("candidate_name", filename)
                return result

            except json.JSONDecodeError as exc:
                return _error_result(filename, f"Model returned invalid JSON: {exc}")
            except Exception as exc:
                if not _is_retryable(exc) or attempt >= max_retries:
                    return _error_result(filename, str(exc))
                delay = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2**attempt)) + random.uniform(0, 1)
                attempt += 1
                await asyncio.sleep(delay)


async def run_batch(
    api_key: str,
    job_description: str,
    resumes: list[tuple[str, str]],
    model: str = DEFAULT_MODEL,
    max_concurrency: int = 5,
    max_retries: int = DEFAULT_MAX_RETRIES,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[dict]:
    """Screen a batch of (filename, resume_text) pairs concurrently.

    Concurrency is bounded by a semaphore (max_concurrency); each individual
    call retries with exponential backoff on rate limits (HTTP 429) and
    transient server errors (5xx).
    """
    total = len(resumes)
    results: list[Optional[dict]] = [None] * total
    completed = 0
    lock = asyncio.Lock()

    client = genai.Client(api_key=api_key)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def worker(index: int, filename: str, text: str) -> None:
        nonlocal completed
        results[index] = await evaluate_resume(
            client, semaphore, filename, text, job_description, model, max_retries
        )
        async with lock:
            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    await asyncio.gather(*(worker(i, fn, txt) for i, (fn, txt) in enumerate(resumes)))

    return results
