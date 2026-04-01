"""
app.py
------
AutoJob AI Agent – Streamlit Web Interface

Entry point for the web application. Run with:
    streamlit run app.py

Layout:
  - Sidebar  : Configuration (API key, search options, memory panel)
  - Main area: Inputs → Agent Logs → Job Results
"""

import sys
import os

# Make sure local modules are importable regardless of working directory
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

from agents.job_agent import run_agent, LOG_INFO, LOG_SUCCESS, LOG_WARNING, LOG_ERROR, LOG_STEP
from utils.memory     import (
    get_search_history,
    get_selected_jobs,
    get_memory_summary,
    reset_memory,
)

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AutoJob AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS – Clean, professional look
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ── Global ── */
[data-testid="stAppViewContainer"] {
    background: #0f1117;
    color: #e8eaf6;
}
[data-testid="stSidebar"] {
    background: #1a1d27;
    border-right: 1px solid #2d3047;
}

/* ── Header banner ── */
.hero-banner {
    background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #1565c0 100%);
    border-radius: 16px;
    padding: 32px 40px;
    margin-bottom: 28px;
    border: 1px solid #3949ab;
    box-shadow: 0 8px 32px rgba(26,35,126,0.4);
}
.hero-banner h1 {
    font-size: 2.4rem;
    font-weight: 800;
    color: #fff;
    margin: 0 0 8px 0;
    letter-spacing: -0.5px;
}
.hero-banner p {
    font-size: 1.05rem;
    color: #90caf9;
    margin: 0;
}

/* ── Section headings ── */
.section-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #90caf9;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 24px 0 12px 0;
    padding-bottom: 6px;
    border-bottom: 2px solid #1e2a45;
}

/* ── Log console ── */
.log-console {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px 20px;
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
    max-height: 280px;
    overflow-y: auto;
}
.log-step    { color: #58a6ff; font-weight: bold; }
.log-success { color: #3fb950; }
.log-info    { color: #8b949e; }
.log-warning { color: #d29922; }
.log-error   { color: #f85149; }

/* ── Job card ── */
.job-card {
    background: #161b27;
    border: 1px solid #21262d;
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 20px;
    transition: border-color 0.2s;
}
.job-card:hover {
    border-color: #3949ab;
}
.job-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 14px;
    gap: 12px;
}
.job-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #e8eaf6;
    margin: 0 0 4px 0;
}
.job-meta {
    color: #8b949e;
    font-size: 0.9rem;
    margin: 0;
}
.score-badge {
    background: linear-gradient(135deg, #1a237e, #283593);
    border: 2px solid #3949ab;
    border-radius: 50px;
    padding: 6px 18px;
    font-size: 1.1rem;
    font-weight: 800;
    color: #90caf9;
    white-space: nowrap;
    text-align: center;
    min-width: 80px;
}
.score-high   { border-color: #2e7d32; color: #69f0ae; background: linear-gradient(135deg, #1b5e20, #2e7d32); }
.score-medium { border-color: #e65100; color: #ffcc02; background: linear-gradient(135deg, #bf360c, #e65100); }
.score-low    { border-color: #b71c1c; color: #ff5252; background: linear-gradient(135deg, #7f0000, #b71c1c); }

/* ── Tags ── */
.tag {
    display: inline-block;
    background: #1e2a45;
    border: 1px solid #2d3047;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.8rem;
    color: #90caf9;
    margin: 3px 4px 3px 0;
}

/* ── Pills for strengths/gaps ── */
.pill-green {
    display: inline-block;
    background: #1b3a24;
    border: 1px solid #2e7d32;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.8rem;
    color: #69f0ae;
    margin: 3px 4px 3px 0;
}
.pill-red {
    display: inline-block;
    background: #3a1b1b;
    border: 1px solid #b71c1c;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.8rem;
    color: #ff5252;
    margin: 3px 4px 3px 0;
}

/* ── Application box ── */
.app-box {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px 20px;
    font-size: 0.88rem;
    color: #c9d1d9;
    white-space: pre-wrap;
    line-height: 1.65;
}

/* ── Run button ── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #1a237e, #1565c0) !important;
    color: white !important;
    border: none !important;
    padding: 14px 36px !important;
    border-radius: 10px !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    width: 100% !important;
    letter-spacing: 0.3px !important;
    transition: opacity 0.2s !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    opacity: 0.88 !important;
}

/* ── Sidebar labels ── */
[data-testid="stSidebar"] label {
    color: #90caf9 !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stNumberInput input {
    background: #0d1117 !important;
    color: #e8eaf6 !important;
    border-color: #21262d !important;
}

/* ── Metric cards ── */
.metric-row {
    display: flex;
    gap: 12px;
    margin: 8px 0 16px 0;
}
.metric-box {
    flex: 1;
    background: #161b27;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 12px 16px;
    text-align: center;
}
.metric-number { font-size: 1.7rem; font-weight: 800; color: #90caf9; }
.metric-label  { font-size: 0.75rem; color: #8b949e; margin-top: 2px; }

/* ── Divider ── */
hr { border-color: #21262d !important; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State Initialisation
# ---------------------------------------------------------------------------
def init_session_state() -> None:
    defaults = {
        "agent_result":   None,
        "agent_logs":     [],
        "is_running":     False,
        "openai_api_key": "",
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

init_session_state()


# ---------------------------------------------------------------------------
# Helper – Score Colour
# ---------------------------------------------------------------------------
def score_class(score: int) -> str:
    if score >= 70:
        return "score-high"
    elif score >= 45:
        return "score-medium"
    return "score-low"


def score_emoji(score: int) -> str:
    if score >= 70:
        return "🟢"
    elif score >= 45:
        return "🟡"
    return "🔴"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")

    # API Key input
    api_key_input = st.text_input(
        "🔑 OpenAI API Key",
        type="password",
        placeholder="sk-...",
        value=st.session_state.openai_api_key,
        help="Your OpenAI API key. Get one at platform.openai.com",
    )
    if api_key_input:
        st.session_state.openai_api_key = api_key_input
        os.environ["OPENAI_API_KEY"] = api_key_input

    # Check env var fallback
    if not st.session_state.openai_api_key and os.getenv("OPENAI_API_KEY"):
        st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY")
        st.success("✅ API key loaded from environment", icon="✅")
    elif st.session_state.openai_api_key:
        st.success("✅ API key configured", icon="✅")
    else:
        st.warning("⚠️ No API key set. AI features will fail.", icon="⚠️")

    st.markdown("---")
    st.markdown("## 🎛️ Search Options")

    top_n = st.slider(
        "Top jobs to process",
        min_value=1, max_value=10, value=3,
        help="How many top-ranked jobs to generate applications for.",
    )

    min_score = st.slider(
        "Minimum relevance score",
        min_value=0, max_value=80, value=0, step=5,
        help="Filter out jobs below this score.",
    )

    generate_apps = st.checkbox(
        "Generate Applications",
        value=True,
        help="Uncheck to only score jobs (faster, saves API calls).",
    )

    st.markdown("---")
    st.markdown("## 🧠 Memory")

    summary = get_memory_summary()

    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-box">
            <div class="metric-number">{summary['total_searches']}</div>
            <div class="metric-label">Searches</div>
        </div>
        <div class="metric-box">
            <div class="metric-number">{summary['total_runs']}</div>
            <div class="metric-label">Runs</div>
        </div>
        <div class="metric-box">
            <div class="metric-number">{summary['selected_jobs']}</div>
            <div class="metric-label">Saved Jobs</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Search history
    history = get_search_history()
    if history:
        with st.expander("🕑 Recent Searches", expanded=False):
            for item in reversed(history[-5:]):
                result_count = item.get("result_count") or item.get("results_count") or 0
                st.markdown(
                    f"**{item['query']}** in *{item['location'] or 'Any'}*  \n"
                    f"<small>{result_count} results · {item['timestamp']}</small>",
                    unsafe_allow_html=True,
                )
                st.markdown("---")

    # Saved / bookmarked jobs
    saved = get_selected_jobs()
    if saved:
        with st.expander(f"⭐ Saved Jobs ({len(saved)})", expanded=False):
            for job in saved:
                st.markdown(f"**{job['title']}** @ {job['company']}")
                if "score" in job:
                    st.markdown(f"Score: {job['score']}/100")
                st.markdown(f"<small>Saved: {job.get('selected_at','')}</small>", unsafe_allow_html=True)
                st.markdown("---")

    if st.button("🗑️ Clear Memory", use_container_width=True):
        reset_memory()
        st.success("Memory cleared!")
        st.rerun()

    st.markdown("---")
    st.markdown(
        "<small style='color:#8b949e'>AutoJob AI Agent v1.0<br>"
        "Built with Streamlit + OpenAI</small>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main Content
# ---------------------------------------------------------------------------

# Hero Banner
st.markdown("""
<div class="hero-banner">
    <h1>🤖 AutoJob AI Agent</h1>
    <p>Intelligent job search, AI-powered relevance scoring, and personalised application generation — all in one place.</p>
</div>
""", unsafe_allow_html=True)

# ── Input Form ──────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1], gap="medium")

with col1:
    job_title_input = st.text_input(
        "💼 Job Title / Keywords",
        placeholder="e.g. Python Developer, ML Engineer, Data Scientist",
        help="Enter the job title or keywords you want to search for.",
    )

with col2:
    location_input = st.text_input(
        "📍 Location",
        placeholder="e.g. Remote, New York, London",
        help="Enter a city, region, or 'Remote'. Leave blank for all locations.",
    )

cv_input = st.text_area(
    "📄 Your CV / Resume",
    placeholder=(
        "Paste your full CV here. Include your skills, experience, education, and achievements.\n\n"
        "Example:\n"
        "John Doe | john@email.com | linkedin.com/in/johndoe\n\n"
        "SKILLS: Python, Machine Learning, TensorFlow, FastAPI, PostgreSQL, AWS\n\n"
        "EXPERIENCE:\n"
        "Senior Software Engineer – Acme Corp (2021–Present)\n"
        "- Led development of real-time data pipeline handling 10M events/day\n"
        "- Reduced API latency by 40% through query optimisation\n\n"
        "EDUCATION:\n"
        "BSc Computer Science – MIT (2017–2021)"
    ),
    height=240,
    help="The more detail you provide, the better the AI scoring and application quality.",
)

# ── Run Button ──────────────────────────────────────────────────────────────
st.markdown("")

col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    run_clicked = st.button(
        "🚀  Run Agent",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.is_running,
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Agent Execution
# ---------------------------------------------------------------------------
if run_clicked:
    # Validate inputs before running
    errors = []
    if not job_title_input.strip():
        errors.append("❌ Please enter a job title or keyword.")
    if not cv_input.strip():
        errors.append("❌ Please paste your CV text.")
    if not st.session_state.openai_api_key:
        errors.append("❌ Please enter your OpenAI API key in the sidebar.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        # Set API key in environment for the tools to use
        os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key
        st.session_state.is_running = True
        st.session_state.agent_logs = []
        st.session_state.agent_result = None

        # ── Live Log Console ──────────────────────────────────────────────
        st.markdown('<div class="section-title">🧠 Agent Reasoning Log</div>', unsafe_allow_html=True)
        log_placeholder = st.empty()

        def render_logs(logs: list) -> str:
            """Render log entries as an HTML console."""
            lines = []
            icons = {
                LOG_STEP:    ("▶", "log-step"),
                LOG_SUCCESS: ("✓", "log-success"),
                LOG_INFO:    ("·", "log-info"),
                LOG_WARNING: ("⚠", "log-warning"),
                LOG_ERROR:   ("✗", "log-error"),
            }
            for entry in logs:
                lvl   = entry.get("level", LOG_INFO)
                msg   = entry.get("message", "")
                icon, css = icons.get(lvl, ("·", "log-info"))
                lines.append(f'<span class="{css}">{icon} {msg}</span>')
            return '<div class="log-console">' + "<br>".join(lines) + "</div>"

        # Collect logs as we go and update the display
        collected_logs = []

        def on_log(entry: dict) -> None:
            collected_logs.append(entry)
            log_placeholder.markdown(render_logs(collected_logs), unsafe_allow_html=True)

        # Run the agent with live log streaming
        with st.spinner("Agent is working..."):
            result = run_agent(
                job_title=job_title_input,
                location=location_input,
                cv=cv_input,
                top_n=top_n,
                min_score=min_score,
                generate_apps=generate_apps,
                log_callback=on_log,
            )

        # Final render of all logs
        log_placeholder.markdown(render_logs(result.get("logs", [])), unsafe_allow_html=True)

        st.session_state.agent_result = result
        st.session_state.agent_logs   = result.get("logs", [])
        st.session_state.is_running   = False

        # Force rerun to refresh memory metrics in sidebar
        st.rerun()


# ---------------------------------------------------------------------------
# Results Display
# ---------------------------------------------------------------------------
result = st.session_state.agent_result

if result:
    # ── Status Banner ──────────────────────────────────────────────────────
    if result.get("status") == "error":
        st.error(f"❌ Agent Error: {result.get('error', 'Unknown error')}")
    elif result.get("jobs_found", 0) == 0:
        st.warning("🔍 No matching jobs found. Try different keywords or a broader location.")
    else:
        jobs = result["jobs"]

        # ── Summary Metrics ────────────────────────────────────────────────
        st.markdown('<div class="section-title">📊 Results Summary</div>', unsafe_allow_html=True)

        avg_score  = sum(j["score"] for j in jobs) // len(jobs) if jobs else 0
        top_score  = jobs[0]["score"] if jobs else 0
        with_apps  = sum(1 for j in jobs if j.get("cover_letter"))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Jobs Found",      result["jobs_found"])
        m2.metric("Avg Match Score", f"{avg_score}/100")
        m3.metric("Top Score",       f"{top_score}/100")
        m4.metric("Applications",    with_apps)

        st.markdown("")

        # ── Logs (if not already shown above) ─────────────────────────────
        if not run_clicked and st.session_state.agent_logs:
            with st.expander("🧠 View Agent Reasoning Log", expanded=False):
                log_icons = {
                    LOG_STEP:    ("▶", "log-step"),
                    LOG_SUCCESS: ("✓", "log-success"),
                    LOG_INFO:    ("·", "log-info"),
                    LOG_WARNING: ("⚠", "log-warning"),
                    LOG_ERROR:   ("✗", "log-error"),
                }
                lines = []
                for entry in st.session_state.agent_logs:
                    lvl = entry.get("level", LOG_INFO)
                    msg = entry.get("message", "")
                    icon, css = log_icons.get(lvl, ("·", "log-info"))
                    lines.append(f'<span class="{css}">{icon} {msg}</span>')
                st.markdown(
                    '<div class="log-console">' + "<br>".join(lines) + "</div>",
                    unsafe_allow_html=True,
                )

        # ── Job Cards ──────────────────────────────────────────────────────
        st.markdown('<div class="section-title">💼 Job Results</div>', unsafe_allow_html=True)

        for rank, job in enumerate(jobs, start=1):
            score     = job.get("score", 0)
            s_class   = score_class(score)
            s_emoji   = score_emoji(score)
            strengths = job.get("strengths", [])
            gaps      = job.get("gaps", [])
            cover     = job.get("cover_letter", "")
            linkedin  = job.get("linkedin_message", "")
            # Generate unique key from rank and company (no 'id' field in real API jobs)
            job_key   = f"{rank}_{job.get('company', 'unknown').replace(' ', '_')[:20]}"

            # Card header
            st.markdown(f"""
            <div class="job-card">
                <div class="job-card-header">
                    <div>
                        <p class="job-title">#{rank} &nbsp; {job['title']}</p>
                        <p class="job-meta">
                            🏢 {job['company']} &nbsp;|&nbsp;
                            📍 {job['location']} &nbsp;|&nbsp;
                            💰 {job.get('salary', 'Not disclosed')} &nbsp;|&nbsp;
                            🕐 {job.get('posted', 'Recently')} &nbsp;|&nbsp;
                            {job.get('type', 'Full-time')}
                        </p>
                    </div>
                    <div class="score-badge {s_class}">{s_emoji} {score}<br><small>/ 100</small></div>
                </div>
            """, unsafe_allow_html=True)

            # Job description
            with st.expander("📋 Job Description", expanded=False):
                st.markdown(job.get("description", "No description available."))

            # Match explanation
            if job.get("explanation"):
                st.markdown(f"**🎯 Match Analysis:** {job['explanation']}")

            # Strengths & Gaps pills
            if strengths or gaps:
                col_s, col_g = st.columns(2)
                with col_s:
                    if strengths:
                        st.markdown("**✅ Strengths:**")
                        pills = " ".join(f'<span class="pill-green">✓ {s}</span>' for s in strengths)
                        st.markdown(pills, unsafe_allow_html=True)
                with col_g:
                    if gaps:
                        st.markdown("**⚠️ Gaps:**")
                        pills = " ".join(f'<span class="pill-red">✗ {g}</span>' for g in gaps)
                        st.markdown(pills, unsafe_allow_html=True)

            # Application Materials
            if cover or linkedin:
                st.markdown("")
                tab_cover, tab_linkedin = st.tabs(["📝 Cover Letter", "💼 LinkedIn Message"])

                with tab_cover:
                    if cover and not cover.startswith("Generation failed") and not cover.startswith("An error"):
                        st.markdown('<div class="app-box">' + cover.replace("\n", "<br>") + "</div>",
                                    unsafe_allow_html=True)
                        st.download_button(
                            label="⬇️ Download Cover Letter",
                            data=cover,
                            file_name=f"cover_letter_{job['company'].replace(' ', '_')}.txt",
                            mime="text/plain",
                            key=f"dl_cover_{job_key}",
                        )
                    else:
                        st.warning(cover or "Cover letter not generated.")

                with tab_linkedin:
                    if linkedin and not linkedin.startswith("Generation failed") and not linkedin.startswith("Error"):
                        st.markdown('<div class="app-box">' + linkedin + "</div>",
                                    unsafe_allow_html=True)
                        char_count = len(linkedin)
                        color = "green" if char_count <= 300 else "red"
                        st.markdown(
                            f"<small style='color:{color}'>Character count: {char_count}/300</small>",
                            unsafe_allow_html=True,
                        )
                        st.download_button(
                            label="⬇️ Download LinkedIn Message",
                            data=linkedin,
                            file_name=f"linkedin_{job['company'].replace(' ', '_')}.txt",
                            mime="text/plain",
                            key=f"dl_linkedin_{job_key}",
                        )
                    else:
                        st.warning(linkedin or "LinkedIn message not generated.")

            # Close card div
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("")  # Spacing between cards

        # ── Footer note ────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown(
            f"<small style='color:#8b949e'>Search: <b>{result['query']}</b> "
            f"· Location: <b>{result['location'] or 'Any'}</b> "
            f"· {result['jobs_found']} job(s) returned</small>",
            unsafe_allow_html=True,
        )

# ── Empty state ────────────────────────────────────────────────────────────
elif not st.session_state.is_running:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #8b949e;">
        <div style="font-size: 4rem; margin-bottom: 16px;">🔍</div>
        <h3 style="color: #90caf9; margin-bottom: 8px;">Ready to find your next job</h3>
        <p>Enter a job title, location, and your CV above — then click <strong style="color:#e8eaf6">Run Agent</strong>.</p>
        <p style="font-size: 0.9rem; margin-top: 20px;">
            The agent will search, score relevance, and generate personalised applications automatically.
        </p>
    </div>
    """, unsafe_allow_html=True)
