"""TRUSTVOICE AI — Security Console (Streamlit entrypoint)."""

import streamlit as st

from risk.config import DEFAULT_BONA_THRESHOLD, DEFAULT_DECISION_BAND
from ui.analyze import render_analyze
from ui.evaluation import render_evaluation
from ui.incidents import render_incidents
from ui.live_monitor import render_live_monitor
from ui.overview import render_overview
from ui.settings import render_settings
from ui.speakers import render_speakers
from ui.theme import css
from utils.state import new_conversation_state

st.set_page_config(
    page_title="TRUSTVOICE AI",
    page_icon="🛡",
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

# Navigation: (group_label, [(store_name, button_key, display_label)])
NAV_GROUPS = (
    (
        "SECURITY OPERATIONS",
        (
            ("Overview", "nav_Overview", "Overview"),
            ("Analyze Audio", "nav_Analyze", "Analyze Audio"),
            ("Live Monitor", "nav_Live", "Live Monitor"),
            ("Trusted Speakers", "nav_Speakers", "Trusted Speakers"),
            ("Incidents", "nav_Incidents", "Incidents"),
        ),
    ),
    (
        "SYSTEM",
        (
            ("Settings", "nav_Settings", "Settings"),
        ),
    ),
)

# Hidden pages (accessible via nav but not in primary sidebar)
HIDDEN_PAGES = {"Evaluation Lab"}


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
        "threshold_source": "prototype default",
        "model_choice": "aasist",
        "ui_nav": "Overview",
        "accuracy_eval": None,
        "analysis_source": "Idle",
        "conversation_state": new_conversation_state(),
        "demo_view": None,
        "edge_case_view": None,
        "transcript_source": "NONE",
        "live_warning": None,
        "asr_filled_transcript": "",
        # speakers
        "speakers_view": "gallery",
        "speakers_selected_id": None,
        "speakers_confirm_delete": None,
        # incidents
        "incidents_selected": None,
        # handshake
        "handshake_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Migrate legacy nav values
    legacy = {
        "Console": "Overview",
        "Reports": "Incidents",
        "Demo Scenarios": "Analyze Audio",
        "Demo scenarios": "Analyze Audio",
    }
    if st.session_state.ui_nav in legacy:
        st.session_state.ui_nav = legacy[st.session_state.ui_nav]


def _render_html(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


# ── Init ────────────────────────────────────────────────────────────────────
init_state()
_render_html(css())

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    # Brand logo
    _render_html("""
    <div class="tv-brand">
      <div class="tv-mark">
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="white" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round"
            d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
      </div>
      <div>
        <div class="tv-brand-name">TRUSTVOICE</div>
        <div class="tv-brand-sub">AI Security</div>
      </div>
    </div>
    """)

    current = st.session_state.ui_nav
    for group_label, items in NAV_GROUPS:
        _render_html(f'<div class="tv-nav-section">{group_label}</div>')
        for store, key, label in items:
            active = current == store
            if st.button(
                label,
                key=key,
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.ui_nav = store
                st.rerun()

    # Bottom status card
    _render_html("""
    <div style="flex:1"></div>
    <div class="tv-side-foot">
      <div class="tv-side-foot-title">
        <span class="tv-online-dot"></span>Prototype system
      </div>
      <div class="tv-side-foot-sub">Analysis services ready</div>
    </div>
    """)

# ── Page routing ────────────────────────────────────────────────────────────
nav = st.session_state.ui_nav

if nav == "Overview":
    render_overview()
elif nav == "Analyze Audio":
    render_analyze()
elif nav == "Live Monitor":
    render_live_monitor()
elif nav == "Trusted Speakers":
    render_speakers()
elif nav == "Incidents":
    render_incidents()
elif nav == "Settings":
    render_settings()
elif nav in {"Evaluation Lab", "Evaluation"}:
    render_evaluation()
else:
    # Fallback — redirect to Overview
    st.session_state.ui_nav = "Overview"
    st.rerun()
