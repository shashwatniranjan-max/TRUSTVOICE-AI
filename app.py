"""TRUSTVOICE AI — Conversation Security Console (Streamlit entrypoint)."""

import streamlit as st

from risk.config import DEFAULT_BONA_THRESHOLD, DEFAULT_DECISION_BAND
from ui.components import render
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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()
render(st, css())

with st.sidebar:
    render(st, """
    <div class="tv-brand">TRUSTVOICE AI
      <span>Security analysis console</span>
    </div>
    """)
    for label in ("Console", "Demo scenarios", "Evaluation", "Reports", "Settings"):
        if st.button(label, key=f"nav_{label}", use_container_width=True):
            st.session_state.ui_nav = label
            st.rerun()
    st.caption(
        "A real voice is not a safe conversation. Authenticity, identity, intent, "
        "behaviour and context are scored separately, then fused as decision support."
    )

nav = st.session_state.ui_nav
if nav == "Console":
    render_console()
elif nav == "Demo scenarios":
    render_demo()
elif nav == "Evaluation":
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
