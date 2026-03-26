# Knowledge Base: The Builder's Edge Coaching Calls

## Context

57 coaching call transcripts (plain text, no speaker labels, ~5,000–15,000 words each) generated from Erin Stetzer's Builder's Edge program. The goal is a personal knowledge base that enables:

1. **Batch analysis** — surfacing core teachings, frameworks, recurring advice, common client challenges, and notable quotes across all sessions
2. **Interactive Q&A** — asking natural language questions and getting synthesized answers with session citations

All processing uses the Claude API locally via terminal. A Streamlit dashboard is deployed at Streamlit Community Cloud for browser-based access.

---

## Architecture: 3-Stage Pipeline

```
Transcripts/          →    Knowledge Base/extractions/   →    Knowledge Base/
  (57 .txt files)           (57 .json files)                  teachings.md
                                                               challenges.md
                                                               advice.md
                                                               quotes.md
```

---

## Stage 1 — Per-Transcript Extraction (`extract.py`)

- Reads each `.txt` transcript from `Transcripts/`
- Sends to `claude-sonnet-4-6` with a structured extraction prompt
- Skips files already extracted (resume-safe)
- Outputs one JSON per session to `Knowledge Base/extractions/`

### JSON Schema

```json
{
  "date": "2025-05-15",
  "title": "Modifications: Control the Process",
  "session_type": "group_coaching | open_workshop | roundtable | guest_speaker",
  "summary": "2-3 sentence overview",
  "teachings": [
    { "concept": "Call them Modifications, not Change Orders", "explanation": "...", "quote": "..." }
  ],
  "actionable_advice": ["specific advice items"],
  "client_challenges": ["challenges raised in this session"],
  "notable_quotes": ["memorable quotes with context"]
}
```

### Observed Token Usage (actual)

| Metric | Value |
|---|---|
| Avg input tokens | ~13,000 |
| Avg output tokens | ~2,200 |
| Total input (57 sessions) | ~741K |
| Total output (57 sessions) | ~125K |
| Estimated cost | ~$4.00–4.50 |

---

## Stage 2 — Aggregate Knowledge Base (`build_kb.py`)

- Reads all extraction JSONs
- Groups and deduplicates across sessions
- Ranks topics/challenges by frequency
- Generates 4 markdown files in `Knowledge Base/`:
  - `teachings.md` — frameworks & mental models, grouped by theme
  - `challenges.md` — common business challenges, ranked by frequency
  - `advice.md` — actionable advice organized by category
  - `quotes.md` — notable quotes with date and session attribution

### Theme Categories (auto-classification)

1. Pricing & Proposals
2. Modifications & Change Orders
3. Cash Flow & Finance
4. Client Relationships
5. Team & Subcontractors
6. Sales & Business Development
7. Operations & Systems
8. Mindset & Leadership
9. Contracts & Legal
10. General Business (fallback)

---

## Stage 3 — Interactive Query (`query.py` / `dashboard.py`)

- **Terminal:** `python3 query.py "What does Erin teach about handling difficult clients?"`
- **Browser:** Streamlit dashboard at Streamlit Community Cloud (password protected)
- Loads all extraction JSONs as context (~28K tokens, fits easily)
- Scores sessions by keyword relevance; pulls top 4 full transcripts for deeper context
- Sends to `claude-opus-4-6` with instructions to synthesize and cite sessions
- Streams answer to terminal/browser with session references
- **Auto-saves every query** to `queries/YYYY-MM-DD_HH-MM-SS - question.md` including model used and token counts

---

## File Structure

```
Stetzer Database/
  Transcripts/                    # 57 .txt files (local only, not in repo)
  Knowledge Base/
    extract.py                    # Stage 1 script
    build_kb.py                   # Stage 2 script
    query.py                      # Stage 3 terminal tool
    dashboard.py                  # Streamlit dashboard
    requirements.txt              # Python dependencies
    README.md                     # this file
    .gitignore                    # excludes secrets, queries, transcripts
    .streamlit/
      secrets.toml                # local secrets (not committed)
    extractions/                  # auto-created by extract.py (committed to repo)
      2024-03-20 - Kick Off Call Erin Stetzer Homes.json
      ...
    teachings.md                  # auto-created by build_kb.py
    challenges.md
    advice.md
    quotes.md
    queries/                      # auto-created by query.py (local only)
      2026-03-18_14-23-01 - What does Erin teach about pricing.md
      ...
```

---

## Key Implementation Details

| Detail | Value |
|---|---|
| Model | `claude-opus-4-6` (query), `claude-sonnet-4-6` (extract) |
| API key | `ANTHROPIC_API_KEY` env var / secret |
| GitHub token | `GITHUB_TOKEN` env var / secret (query persistence) |
| SDK | `anthropic`, `requests` Python packages |
| Python | 3.12 |
| Streaming | Yes — all API calls stream to avoid timeouts |
| Resume-safe | `extract.py` skips JSONs that already exist |
| Full transcripts in query | Top 4 by keyword relevance score |
| Query storage | GitHub-backed (persists across redeploys) |
| Layout | Centered (mobile-friendly) |

---

## Build Notes & Lessons Learned

- **Prompt formatting bug**: The extraction prompt contained JSON examples with `{curly braces}` that conflicted with Python's `str.format()`. Fixed by using `.replace()` instead of `.format()` for variable substitution.
- **API key**: Must be in `~/.zshrc` as `export ANTHROPIC_API_KEY="sk-ant-..."` for persistence. After editing `~/.zshrc`, run `source ~/.zshrc` or open a new terminal. Use `echo $ANTHROPIC_API_KEY` to verify it's set before running scripts.
- **Python command**: Use `python3` and `python3 -m pip`, not `python` or `pip` (not available on this system).

---

## Run Order

```bash
cd "/Users/alexcacciamani/Desktop/Agents/Stetzer Database/Knowledge Base"

python3 extract.py      # Stage 1 (~15-30 min, ~$4)
python3 build_kb.py     # Stage 2 (seconds)
python3 query.py "Your question here"   # Stage 3
```

---

## Dashboard (Streamlit)

The dashboard provides a browser-based interface with 5 tabs:

- **Overview** — session count, date range, session types, queries run
- **Query** — ask questions, streams answer from Claude, auto-saves result
- **Query History** — browse all saved queries with full answers
- **Sessions** — browse/search all 57 session extractions
- **Knowledge Base** — view teachings, challenges, advice, and quotes markdown files

### Running Locally

```bash
cd "/Users/alexcacciamani/Desktop/Agents/Stetzer Database/Knowledge Base"
streamlit run dashboard.py
```

### Deployment

- **GitHub repo:** https://github.com/alexcacciamani/stetzer-knowledge-base (public)
- **Live URL:** https://stetzer-knowledge-base-9jkfvhst3b6wn9xmuckftw.streamlit.app
- **Hosted at:** Streamlit Community Cloud
- **Password:** set via `APP_PASSWORD` secret
- **API key:** set via `ANTHROPIC_API_KEY` secret in Streamlit Cloud dashboard

### Secrets

Local (`.streamlit/secrets.toml`, never committed):
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
APP_PASSWORD = "stetzer"
GITHUB_TOKEN = "github_pat_..."
```

Streamlit Cloud: set all three keys under App Settings → Secrets.

`GITHUB_TOKEN` requires a GitHub Personal Access Token with `repo` scope — generate at github.com/settings/tokens.

### Custom Domain (optional)

To use a subdomain like `stetzer.yourdomain.com`:
1. In Streamlit Cloud app settings → add custom domain
2. Add a CNAME record in your DNS pointing `stetzer` → the Streamlit-provided target

### Updating the Deployed App

After any local changes, push to GitHub and Streamlit will auto-redeploy:

```bash
cd "/Users/alexcacciamani/Desktop/Agents/Stetzer Database/Knowledge Base"
git add .
git commit -m "your message"
git push
```

---

## Status

| Component | Status | Date |
|---|---|---|
| Stage 1 — extract.py | ✅ Complete (57/57 sessions) | 2026-03-26 |
| Stage 2 — build_kb.py | ✅ Complete | 2026-03-26 |
| Stage 3 — query.py | ✅ Tested and working | 2026-03-26 |
| Dashboard — dashboard.py | ✅ Live on Streamlit Community Cloud | 2026-03-26 |
| Query persistence | ✅ GitHub-backed, survives redeploys | 2026-03-26 |
| Mobile layout | ✅ Centered layout enabled | 2026-03-26 |

### Adding New Transcripts

When new coaching call recordings become available:

1. Add the `.txt` transcript to `Transcripts/` using the same naming convention: `YYYY-MM-DD - Session Title Erin Stetzer Homes.txt`
2. Run `python3 extract.py` — it will skip all existing JSONs and only process the new file
3. Run `python3 build_kb.py` — regenerates all 4 markdown files to include the new session
4. No changes to any script required
