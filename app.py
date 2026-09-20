"""TRUSTVOICE AI — Conversation Security Console (Streamlit entrypoint)."""

import streamlit as st

from risk.config import DEFAULT_BONA_THRESHOLD, DEFAULT_DECISION_BAND
from ui.components import analysis_mode, render
from ui.console import render_console, render_demo
from ui.evaluation import render_evaluation
from ui.reports import render_reports
from ui.settings import render_settings
from ui.theme import css
from utils.state import new_conversation_state

st.set_page_config(
    page_title="TRUSTVOICE AI",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

NEUTRAL_FACTORS = {
    "Voice Authenticity": 76,
    "Speaker Identity": 76,
    "Intent Safety": 96,
    "Behaviour Safety": 94,
    "Context Safety": 93,
}

NAV_GROUPS = (
    (
        "Workspace",
        (
            ("Console", "nav_Console", "Console"),
            ("Demo Scenarios", "nav_Demo Scenarios", "Demo Scenarios"),
            ("Evaluation Lab", "nav_Evaluation", "Evaluation Lab"),
        ),
    ),
    (
        "Output",
        (
            ("Reports", "nav_Reports", "Reports"),
            ("Settings", "nav_Settings", "Settings"),
        ),
    ),
)


def init_state():
    defaults = {
        "score": None,
        "scenario": "Awaiting analysis",
        "history": [],
        "analysis_done": False,
        "last_analysis": None,
        "last_result": None,
        "transcript": "",
        "factors": dict(NEUTRAL_FACTORS),
        "action_status": "CONTINUE",
        "handshake_result": None,
        "incident_report": None,
        "incident_report_pdf": None,
        "incident_report_filename": "trustvoice_incident_report.pdf",
        "intent_prediction": None,
        "risk_explanation": [],
        "bona_threshold": DEFAULT_BONA_THRESHOLD,
        "decision_band": DEFAULT_DECISION_BAND,
        "threshold_source": "default (uncalibrated)",
        "model_choice": "aasist",
        "ui_nav": "Console",
        "accuracy_eval": None,
        "analysis_source": "Idle",
        "conversation_state": new_conversation_state(),
        "demo_view": None,
        "edge_case_view": None,
        "transcript_source": "NONE",
        "live_warning": None,
        "asr_filled_transcript": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.ui_nav in {"Demo scenarios", "Evaluation"}:
        st.session_state.ui_nav = (
            "Demo Scenarios" if st.session_state.ui_nav == "Demo scenarios" else "Evaluation Lab"
        )


init_state()
render(st, css())

mode = analysis_mode(st.session_state.get("analysis_source"))
with st.sidebar:
    render(st, """
    <div class="tv-brand">
      <div class="tv-mark">TV</div>
      <div>
        <strong>TRUSTVOICE AI</strong>
        <span>Conversation Security</span>
      </div>
    </div>
    """)
    current = st.session_state.ui_nav
    for group, items in NAV_GROUPS:
        render(st, f'<div class="tv-nav-label">{group}</div>')
        for store, key, label in items:
            if st.button(
                label,
                key=key,
                use_container_width=True,
                type="primary" if current == store else "secondary",
            ):
                st.session_state.ui_nav = store
                st.rerun()
    render(st, f"""
    <div class="tv-side-foot">
      <div class="tv-status"><span class="tv-dot"></span>Analysis Engine Online</div>
      <div>Mode: {mode}</div>
      <div style="margin-top:8px">SIH prototype · decision support only · not a certified fraud verdict · does not intercept cellular calls</div>
    </div>
    """)

nav = st.session_state.ui_nav
if nav == "Console":
    render_console()
elif nav == "Demo Scenarios":
    render_demo()
elif nav in {"Evaluation Lab", "Evaluation"}:
    render_evaluation()
elif nav == "Reports":
    render_reports()
elif nav == "Settings":
    render_settings()

render(st, """
<div class="tv-footer">
  TRUSTVOICE AI · SIH prototype · local processing · not a certified fraud verdict ·
  does not intercept ordinary cellular calls
</div>
""")
