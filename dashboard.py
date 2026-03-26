#!/usr/bin/env python3
"""
Builder's Edge Knowledge Base — Streamlit Dashboard
Run: streamlit run dashboard.py
"""

import base64
import json
import os
from datetime import datetime
from pathlib import Path

import anthropic
import requests
import streamlit as st

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
EXTRACTIONS_DIR = BASE_DIR / "extractions"
TRANSCRIPTS_DIR = BASE_DIR.parent / "Transcripts"
QUERIES_DIR = BASE_DIR / "queries"
GITHUB_OWNER = "alexcacciamani"
GITHUB_REPO = "stetzer-knowledge-base"
GITHUB_QUERIES_PATH = "queries"
KB_FILES = {
    "Teachings": BASE_DIR / "teachings.md",
    "Challenges": BASE_DIR / "challenges.md",
    "Advice": BASE_DIR / "advice.md",
    "Quotes": BASE_DIR / "quotes.md",
}
MODEL = "claude-opus-4-6"
MAX_FULL_TRANSCRIPTS = 4

SYSTEM_PROMPT = """You are a knowledgeable assistant with deep expertise in Erin Stetzer's Builder's Edge coaching program. You have access to structured summaries of every coaching call session, and in some cases the full transcripts.

When answering questions:
1. Synthesize across all relevant sessions — don't just describe one
2. Cite specific sessions by date and title (e.g., "2025-05-15 — Modifications: Control the Process")
3. Use direct quotes when available to ground your answer
4. Be concrete and practical — this is business coaching content
5. If the question touches on something Erin teaches repeatedly, note the pattern across sessions
6. If you don't find enough relevant content, say so honestly

Format your response clearly with headers if the answer has multiple parts."""


# ── Data loading ───────────────────────────────────────────────────────────
@st.cache_data
def load_extractions():
    records = []
    for p in sorted(EXTRACTIONS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["_source_file"] = p.stem
            records.append(data)
        except Exception:
            pass
    return records


def _github_headers():
    token = st.secrets.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def load_queries():
    """Load queries from GitHub (primary) with local filesystem fallback."""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_QUERIES_PATH}"
    try:
        resp = requests.get(url, headers=_github_headers(), timeout=10)
        if resp.status_code == 200:
            files = sorted(resp.json(), key=lambda x: x["name"], reverse=True)
            queries = []
            for f in files:
                if f["name"].endswith(".md"):
                    content_resp = requests.get(f["download_url"], timeout=10)
                    if content_resp.status_code == 200:
                        queries.append({"filename": f["name"], "content": content_resp.text})
            return queries
    except Exception:
        pass

    # Fallback: local filesystem
    QUERIES_DIR.mkdir(exist_ok=True)
    queries = []
    for f in sorted(QUERIES_DIR.glob("*.md"), reverse=True):
        try:
            queries.append({"filename": f.name, "content": f.read_text(encoding="utf-8")})
        except Exception:
            pass
    return queries


# ── KB helper functions (mirrored from query.py) ───────────────────────────
def build_context_block(records):
    lines = ["## Session Summaries (all sessions)\n"]
    for r in sorted(records, key=lambda x: x.get("date", "")):
        lines.append(f"### {r.get('date', '?')} — {r.get('title', '?')}")
        lines.append(f"**Type:** {r.get('session_type', '?')}")
        lines.append(f"**Summary:** {r.get('summary', '')}")
        if r.get("teachings"):
            lines.append("**Teachings:**")
            for t in r["teachings"]:
                lines.append(f"- *{t.get('concept', '')}*: {t.get('explanation', '')}")
                if t.get("quote"):
                    lines.append(f'  > "{t["quote"]}"')
        if r.get("actionable_advice"):
            lines.append("**Actionable Advice:**")
            for a in r["actionable_advice"]:
                lines.append(f"- {a}")
        if r.get("client_challenges"):
            lines.append("**Client Challenges:**")
            for c in r["client_challenges"]:
                lines.append(f"- {c}")
        if r.get("notable_quotes"):
            lines.append("**Notable Quotes:**")
            for q in r["notable_quotes"]:
                lines.append(f"- {q}")
        lines.append("")
    return "\n".join(lines)


def score_relevance(record, query_lower):
    score = 0
    text_blob = " ".join([
        record.get("title", ""),
        record.get("summary", ""),
        " ".join(t.get("concept", "") for t in record.get("teachings", [])),
        " ".join(t.get("explanation", "") for t in record.get("teachings", [])),
        " ".join(record.get("actionable_advice", [])),
        " ".join(record.get("client_challenges", [])),
        " ".join(record.get("notable_quotes", [])),
    ]).lower()
    for word in query_lower.split():
        if len(word) > 3 and word in text_blob:
            score += text_blob.count(word)
    return score


def load_full_transcripts(records, query, n):
    if n == 0:
        return ""
    query_lower = query.lower()
    scored = sorted(records, key=lambda r: score_relevance(r, query_lower), reverse=True)
    top = scored[:n]
    blocks = ["\n## Full Transcripts (most relevant sessions)\n"]
    for record in top:
        source_stem = record.get("_source_file", "")
        txt_candidates = list(TRANSCRIPTS_DIR.glob(f"{source_stem}*.txt"))
        if not txt_candidates:
            date = record.get("date", "")
            if date:
                txt_candidates = list(TRANSCRIPTS_DIR.glob(f"{date}*.txt"))
        if not txt_candidates:
            continue
        txt_path = txt_candidates[0]
        try:
            content = txt_path.read_text(encoding="utf-8", errors="replace")
            title = f"{record.get('date', '?')} — {record.get('title', txt_path.name)}"
            blocks.append(f"### FULL TRANSCRIPT: {title}")
            blocks.append(content)
            blocks.append("")
        except Exception:
            pass
    return "\n".join(blocks)


def save_query(query, answer, usage):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_q = "".join(c if c.isalnum() or c in " -" else "" for c in query)[:60].strip()
    filename = f"{timestamp} - {safe_q}.md"
    content = (
        f"# {query}\n\n"
        f"*{datetime.now().strftime('%Y-%m-%d %H:%M')} · Model: {MODEL} · "
        f"Tokens: {usage.input_tokens:,} in / {usage.output_tokens:,} out*\n\n"
        f"{answer}\n"
    )

    # Save to GitHub
    token = st.secrets.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if token:
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_QUERIES_PATH}/{filename}"
        encoded = base64.b64encode(content.encode()).decode()
        requests.put(url, headers=_github_headers(), timeout=10,
                     json={"message": f"Add query: {filename}", "content": encoded})

    # Also save locally
    QUERIES_DIR.mkdir(exist_ok=True)
    (QUERIES_DIR / filename).write_text(content, encoding="utf-8")

    return filename


# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Builder's Edge Knowledge Base",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ── Password gate ───────────────────────────────────────────────────────────
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.title("Builder's Edge Knowledge Base")
    st.caption("Erin Stetzer — Coaching Call Sessions")
    pwd = st.text_input("Password", type="password", key="pwd_input")
    if st.button("Enter", type="primary"):
        expected = st.secrets.get("APP_PASSWORD") or os.environ.get("APP_PASSWORD", "")
        if pwd == expected:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False


if not check_password():
    st.stop()

st.title("Builder's Edge Knowledge Base")
st.caption("Erin Stetzer — Coaching Call Sessions")

records = load_extractions()

tab_overview, tab_query, tab_history, tab_sessions, tab_kb = st.tabs([
    "Overview", "Query", "Query History", "Sessions", "Knowledge Base"
])


# ── Overview ───────────────────────────────────────────────────────────────
with tab_overview:
    dates = sorted(r.get("date", "") for r in records if r.get("date"))
    queries_saved = len(list(QUERIES_DIR.glob("*.md"))) if QUERIES_DIR.exists() else 0
    session_types = {}
    for r in records:
        t = r.get("session_type", "unknown")
        session_types[t] = session_types.get(t, 0) + 1

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sessions", len(records))
    col2.metric("Date Range", f"{dates[0][:7]} → {dates[-1][:7]}" if dates else "—")
    col3.metric("Queries Run", queries_saved)
    col4.metric("Query Model", MODEL.replace("claude-", ""))

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Session Types")
        for stype, count in sorted(session_types.items(), key=lambda x: -x[1]):
            st.progress(count / len(records), text=f"{stype}: {count}")

    with col_right:
        st.subheader("Sessions by Year")
        by_year = {}
        for r in records:
            year = r.get("date", "")[:4]
            if year:
                by_year[year] = by_year.get(year, 0) + 1
        for year, count in sorted(by_year.items()):
            st.progress(count / len(records), text=f"{year}: {count} sessions")


# ── Query ──────────────────────────────────────────────────────────────────
with tab_query:
    st.subheader("Ask the Knowledge Base")

    query_input = st.text_area(
        "Your question",
        height=80,
        placeholder="What does Erin teach about pricing a new project?",
    )

    if st.button("Ask", type="primary", disabled=not query_input.strip()):
        query = query_input.strip()

        with st.spinner("Building context..."):
            context = build_context_block(records)
            full_tx_context = load_full_transcripts(records, query, MAX_FULL_TRANSCRIPTS)

        user_message = (
            f"Here is the knowledge base from all coaching call sessions:\n\n"
            f"{context}\n\n{full_tx_context}\n\n---\n\n"
            f"Question: {query}\n\nPlease provide a thorough, synthesized answer with specific session citations."
        )

        api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)

        st.markdown("---")
        st.subheader("Answer")

        answer_placeholder = st.empty()
        full_answer = ""
        final_usage = None

        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for text in stream.text_stream:
                full_answer += text
                answer_placeholder.markdown(full_answer + "▌")
            final = stream.get_final_message()
            final_usage = final.usage

        answer_placeholder.markdown(full_answer)

        st.caption(
            f"Model: {MODEL} · "
            f"Tokens: {final_usage.input_tokens:,} in / {final_usage.output_tokens:,} out"
        )

        saved_name = save_query(query, full_answer, final_usage)
        st.success(f"Saved → queries/{saved_name}")


# ── Query History ──────────────────────────────────────────────────────────
with tab_history:
    st.subheader("Query History")

    query_files = load_queries()

    if not query_files:
        st.info("No queries saved yet. Ask a question in the Query tab.")
    else:
        st.caption(f"{len(query_files)} saved queries")
        for q in query_files:
            name = q["filename"].replace(".md", "")
            parts = name.split(" - ", 1)
            # Show timestamp + question as label
            timestamp_part = parts[0].replace("_", " ") if len(parts) > 1 else ""
            question_part = parts[1] if len(parts) > 1 else name
            label = f"{timestamp_part} — {question_part}" if timestamp_part else name
            with st.expander(label):
                st.markdown(q["content"])


# ── Sessions ───────────────────────────────────────────────────────────────
with tab_sessions:
    st.subheader("All Sessions")

    col1, col2 = st.columns(2)
    all_types = sorted(set(r.get("session_type", "unknown") for r in records))
    selected_type = col1.selectbox("Filter by type", ["All"] + all_types)
    search_term = col2.text_input("Search", placeholder="pricing, subcontractors...")

    filtered = records
    if selected_type != "All":
        filtered = [r for r in filtered if r.get("session_type") == selected_type]
    if search_term:
        term = search_term.lower()
        filtered = [r for r in filtered if term in json.dumps(r).lower()]

    filtered = sorted(filtered, key=lambda r: r.get("date", ""), reverse=True)
    st.caption(f"Showing {len(filtered)} of {len(records)} sessions")

    for r in filtered:
        label = f"{r.get('date', '?')} — {r.get('title', '?')}"
        with st.expander(label):
            st.caption(f"Type: {r.get('session_type', '?')}")
            st.write(r.get("summary", ""))

            if r.get("teachings"):
                st.markdown("**Teachings**")
                for t in r["teachings"]:
                    st.markdown(f"- **{t.get('concept', '')}**: {t.get('explanation', '')}")
                    if t.get("quote"):
                        st.markdown(f'  > *"{t["quote"]}"*')

            if r.get("actionable_advice"):
                st.markdown("**Actionable Advice**")
                for a in r["actionable_advice"]:
                    st.markdown(f"- {a}")

            if r.get("notable_quotes"):
                st.markdown("**Notable Quotes**")
                for q in r["notable_quotes"]:
                    st.markdown(f"> {q}")


# ── Knowledge Base ─────────────────────────────────────────────────────────
with tab_kb:
    st.subheader("Aggregated Knowledge Base")
    kb_tab_names = list(KB_FILES.keys())
    kb_tabs = st.tabs(kb_tab_names)
    for i, (name, path) in enumerate(KB_FILES.items()):
        with kb_tabs[i]:
            if path.exists():
                st.markdown(path.read_text(encoding="utf-8"))
            else:
                st.warning(f"{path.name} not found. Run build_kb.py first.")
