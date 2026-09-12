"""Streamlit UI for batch resume screening against a job description via an LLM."""

from __future__ import annotations

import asyncio

import pandas as pd
import streamlit as st

from pdf_utils import extract_text_from_pdf
from providers import PROVIDERS

MAX_RESUMES = 1000

st.set_page_config(page_title="AI Resume Screener", page_icon="🧾", layout="wide")

with st.sidebar:
    st.header("Settings")
    provider_name = st.selectbox("AI Provider", list(PROVIDERS.keys()))
    provider = PROVIDERS[provider_name]
    api_key = st.text_input(
        provider.key_label,
        type="password",
        help=provider.key_help,
        key=f"api_key_{provider_name}",
    )
    with st.expander("Advanced settings"):
        model = st.text_input(
            "Model",
            value=provider.module.DEFAULT_MODEL,
            key=f"model_{provider_name}",
        )
        max_concurrency = st.slider("Max concurrent requests", 1, 20, 5, key="max_concurrency")
        max_retries = st.slider("Max retries on rate limit / server errors", 0, 8, 5, key="max_retries")

st.title("🧾 AI Resume Screener")
st.caption(f"Evidence-based resume screening at scale, powered by {provider_name}.")

st.subheader("1. Job Description")
job_description = st.text_area(
    "Paste the full job description, including must-have and nice-to-have requirements.",
    height=250,
    placeholder="e.g. Senior Backend Engineer\n\nMust-Haves:\n- 5+ years of Python\n- ...\n\nNice-to-Haves:\n- AWS experience\n- ...",
)

st.subheader("2. Upload Resumes (PDF)")
uploaded_files = st.file_uploader(
    f"Upload up to {MAX_RESUMES} PDF resumes",
    type=["pdf"],
    accept_multiple_files=True,
)

run_clicked = st.button(
    "Run Screening",
    type="primary",
    disabled=not (api_key and job_description and uploaded_files),
)

if "results_df" not in st.session_state:
    st.session_state.results_df = None

if run_clicked:
    if len(uploaded_files) > MAX_RESUMES:
        st.error(f"Please upload at most {MAX_RESUMES} resumes at a time.")
    else:
        resumes: list[tuple[str, str]] = []
        extraction_errors: list[tuple[str, str]] = []
        with st.spinner("Extracting text from PDFs..."):
            for f in uploaded_files:
                text, err = extract_text_from_pdf(f.read(), f.name)
                if err:
                    extraction_errors.append((f.name, err))
                else:
                    resumes.append((f.name, text))

        for name, err in extraction_errors:
            st.warning(f"Skipped **{name}**: {err}")

        if resumes:
            progress_bar = st.progress(0.0, text="Starting screening...")

            def on_progress(done: int, total: int) -> None:
                progress_bar.progress(done / total, text=f"Screened {done}/{total} resumes...")

            results = asyncio.run(
                provider.module.run_batch(
                    api_key=api_key,
                    job_description=job_description,
                    resumes=resumes,
                    model=model,
                    max_concurrency=max_concurrency,
                    max_retries=max_retries,
                    progress_callback=on_progress,
                )
            )
            progress_bar.empty()

            df = pd.DataFrame(results)
            df = df.sort_values("match_score", ascending=False).reset_index(drop=True)
            st.session_state.results_df = df
        else:
            st.error("No resumes could be read. Please check the uploaded files.")

if st.session_state.results_df is not None:
    df = st.session_state.results_df
    st.subheader("3. Leaderboard")

    status_counts = df["status"].value_counts()
    cols = st.columns(4)
    cols[0].metric("Total Candidates", len(df))
    cols[1].metric("Shortlisted", int(status_counts.get("Shortlisted", 0)))
    cols[2].metric("Flagged", int(status_counts.get("Flagged", 0)))
    cols[3].metric("Rejected", int(status_counts.get("Rejected", 0)) + int(status_counts.get("Error", 0)))

    display_cols = [c for c in ["candidate_name", "filename", "match_score", "status", "years_experience_estimated"] if c in df.columns]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

    st.subheader("4. Candidate Details")
    for _, row in df.iterrows():
        header = f"{row.get('candidate_name', 'Unknown')} — {row.get('match_score', '?')}% — {row.get('status', '?')}"
        with st.expander(header):
            st.markdown(f"**File:** {row.get('filename')}")
            if pd.notna(row.get("years_experience_estimated")):
                st.markdown(f"**Estimated years of experience:** {row.get('years_experience_estimated')}")

            st.markdown("**Strengths:**")
            for s in row.get("strengths") or []:
                st.markdown(f"- {s}")

            st.markdown("**Weaknesses / Gaps:**")
            for w in row.get("weaknesses") or []:
                st.markdown(f"- {w}")

            if row.get("must_haves_met"):
                st.markdown("**Must-Have Requirements:**")
                for item in row["must_haves_met"]:
                    icon = "✅" if item.get("met") else "❌"
                    st.markdown(f"{icon} {item.get('requirement')} — _{item.get('evidence')}_")

            if row.get("nice_to_haves_met"):
                st.markdown("**Nice-to-Have Requirements:**")
                for item in row["nice_to_haves_met"]:
                    icon = "✅" if item.get("met") else "➖"
                    st.markdown(f"{icon} {item.get('requirement')} — _{item.get('evidence')}_")

    st.subheader("5. Export")
    export_df = df[[c for c in df.columns if c not in ("must_haves_met", "nice_to_haves_met")]].copy()
    for col in ("strengths", "weaknesses"):
        if col in export_df.columns:
            export_df[col] = export_df[col].apply(lambda x: "; ".join(x) if isinstance(x, list) else x)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    st.download_button("Export to CSV", data=csv_bytes, file_name="resume_screening_results.csv", mime="text/csv")
