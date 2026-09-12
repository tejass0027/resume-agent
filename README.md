# AI Resume Screener

A Streamlit app that screens up to 1,000 PDF resumes against a job description using Gemini, and returns a sorted, evidence-backed leaderboard.

Each resume is checked against the job description's Must-Have and Nice-to-Have requirements. Gemini is forced (via a JSON response schema) to return a strict structured evaluation, quoting verbatim evidence from the resume for every requirement rather than guessing — so a candidate is only credited with a skill or years of experience if it's explicitly written down.

## Features

- Paste a job description, upload PDF resumes, click **Run Screening**.
- Resumes are screened concurrently (bounded by a semaphore) with automatic exponential backoff on rate limits and transient server errors.
- Each candidate gets a `match_score` (0-100), a `status` (`Shortlisted` / `Flagged` / `Rejected`), strengths, weaknesses, and a per-requirement breakdown with evidence quotes.
- Leaderboard sorted by match score, with expandable per-candidate detail.
- Export results to CSV.
- Each user supplies their own Gemini API key at runtime (entered in the sidebar, kept only in session memory) — no shared billing. Gemini has a free tier, so this can be run at no cost.

## Project layout

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI |
| `gemini_client.py` | Prompt construction, response schema, async batch screening with concurrency + retry/backoff |
| `pdf_utils.py` | PDF text extraction (PyMuPDF) |
| `requirements.txt` | Python dependencies |

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Open the app in your browser, enter your [Gemini API key](https://aistudio.google.com/apikey) (free) in the sidebar, paste a job description, upload resumes, and run the screening.

## Notes

- Resumes must be text-based PDFs; scanned image PDFs without a text layer will be skipped (no OCR).
- The `Advanced settings` panel in the sidebar lets you change the model, concurrency limit, and retry count. Default model is `gemini-2.5-flash`; free-tier rate limits are fairly low, so keep concurrency modest if you're on the free tier.
