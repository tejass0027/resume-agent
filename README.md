# AI Resume Screener

## What it does

You give it a job description and a stack of resumes (PDF files) — it reads every resume, compares it against the job's requirements, and hands you back a ranked shortlist.

For each candidate you get:
- A **match score** out of 100
- A **status**: Shortlisted, Flagged, or Rejected
- Their **strengths** and **weaknesses** for this specific role
- A **quote pulled directly from their resume** as proof for each requirement — it never guesses or assumes a skill just because of a job title. If the resume doesn't say it, it's marked as not met.

Results show up as a leaderboard, best match first, and can be downloaded as a CSV file for the rest of your team.

You can screen up to 1,000 resumes in one go, and you choose which AI does the reading — Google Gemini, Anthropic Claude, or OpenAI ChatGPT.

## How to make it work

1. **Get a free API key** from whichever AI you want to use:
   - Gemini (free): [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   - Claude: [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
   - ChatGPT: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

2. **One-time setup** — open a terminal in this folder and run:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Start the app**:
   ```bash
   streamlit run app.py
   ```
   This opens the app in your browser.

4. In the sidebar, **choose your AI provider** and **paste in your API key**.

5. **Paste the job description** and **upload the resumes** (PDF only).

6. Click **Run Screening** and wait for the leaderboard to fill in.

7. Click **Export to CSV** to save the results.

## Good to know

- Your API key is never saved — you enter it fresh each time you open the app, and it's only used to talk to the AI provider you picked.
- Resumes need to be real, text-based PDFs. A scanned photo/image of a resume with no selectable text won't work.
- If you're on a free-tier API key, lower "Max concurrent requests" in the sidebar's Advanced settings so you don't hit rate limits when screening a large batch.
