"""Dark analytics dashboard theme for TRUSTVOICE AI."""

COLORS = {
    "bg": "#0B0F14",
    "bg2": "#0D1219",
    "surface": "#111821",
    "surface2": "#151C26",
    "elevated": "#192230",
    "border": "#253041",
    "text": "#E8EDF5",
    "muted": "#9AA6B5",
    "dim": "#667384",
    "accent": "#3D7DE8",
    "accent2": "#2A4A7A",
    "green": "#3FA36A",
    "amber": "#C49A3C",
    "red": "#C45C5C",
    "gray": "#667384",
}

SPACING = {"xs": "4px", "sm": "8px", "md": "12px", "lg": "16px", "xl": "24px"}
RADIUS = "8px"
FONT = '"IBM Plex Sans", "Segoe UI", sans-serif'

STATUS_COLOR = {
    "LOW": COLORS["green"],
    "CONTINUE": COLORS["green"],
    "LIKELY AUTHENTIC": COLORS["green"],
    "GOOD": COLORS["green"],
    "COMPLETED": COLORS["green"],
    "ONLINE": COLORS["green"],
    "VERIFIED": COLORS["green"],
    "ELEVATED": COLORS["amber"],
    "WARN": COLORS["amber"],
    "INCONCLUSIVE": COLORS["amber"],
    "INCONCLUSIVE / AUDIO QUALITY": COLORS["amber"],
    "ANALYZING": COLORS["accent"],
    "MEDIUM": COLORS["amber"],
    "HIGH": COLORS["red"],
    "CRITICAL": COLORS["red"],
    "VERIFY": COLORS["red"],
    "CRITICAL INTERVENTION": COLORS["red"],
    "LIKELY SPOOF": COLORS["red"],
    "FAILED": COLORS["red"],
    "UNAVAILABLE": COLORS["gray"],
    "NOT_AVAILABLE": COLORS["gray"],
    "UNVERIFIED": COLORS["gray"],
    "QUEUED": COLORS["gray"],
    "MISMATCH": COLORS["red"],
}


def status_color(label: str) -> str:
    return STATUS_COLOR.get(str(label).upper(), COLORS["gray"])


def css() -> str:
    c = COLORS
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{
  background: {c['bg']};
  color: {c['text']};
  font-family: {FONT};
  font-size: 15px;
}}
[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{
  max-width: 1360px;
  padding: 0.7rem 1.35rem 1.6rem;
}}
p, label, .stMarkdown, [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p {{
  font-size: 14px !important;
}}
[data-testid="stCaptionContainer"], .stCaption, [data-testid="stCaptionContainer"] p {{
  color: {c['muted']} !important;
  font-size: 13px !important;
}}
.stTextArea textarea, .stTextInput input, [data-baseweb="select"] {{
  font-size: 14px !important;
}}
[data-testid="stFileUploader"] label, [data-testid="stFileUploader"] small,
[data-testid="stFileUploaderDropzone"] {{
  font-size: 14px !important;
}}
[data-testid="stSidebar"] {{
  background: {c['bg2']};
  border-right: 1px solid {c['border']};
}}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
  padding: 1rem 0.8rem 1.2rem;
}}
section[data-testid="stSidebar"] {{ min-width: 248px !important; }}
[data-testid="stSidebar"] .stButton {{ margin-bottom: 4px; }}
[data-testid="stSidebar"] .stButton > button {{
  min-height: 40px !important;
  font-weight: 500 !important;
  font-size: 14px !important;
  justify-content: flex-start !important;
  padding: 0 12px !important;
  background: transparent !important;
  color: {c['muted']} !important;
  border: 0 !important;
  border-radius: 6px !important;
  box-shadow: none !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
  background: {c['surface']} !important;
  color: {c['text']} !important;
}}
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {{
  background: rgba(61,125,232,0.12) !important;
  color: {c['text']} !important;
  box-shadow: inset 3px 0 0 {c['accent']} !important;
}}
.stButton > button {{
  border-radius: 6px !important;
  border: 1px solid {c['border']} !important;
  background: {c['surface2']} !important;
  color: {c['text']} !important;
  min-height: 40px !important;
  font-weight: 500 !important;
  font-size: 14px !important;
  box-shadow: none !important;
}}
.stButton > button:hover {{
  border-color: {c['accent']} !important;
}}
button[kind="primary"], button[data-testid="baseButton-primary"] {{
  border-color: {c['accent']} !important;
  background: {c['accent2']} !important;
}}
[data-testid="stFileUploader"] {{
  border: 1px dashed {c['border']};
  border-radius: {RADIUS};
  background: {c['surface2']};
}}
.stProgress > div > div > div > div {{ background: {c['accent']}; }}
div[data-testid="stAlert"] {{
  font-size: 14px !important;
  background: {c['surface2']} !important;
  border: 1px solid {c['border']} !important;
  color: {c['text']} !important;
}}
.stExpander {{
  border: 1px solid {c['border']} !important;
  border-radius: {RADIUS} !important;
  background: {c['surface']} !important;
}}

.tv-brand {{
  display: flex; gap: 10px; align-items: flex-start;
  padding: 4px 6px 16px; color: {c['text']};
}}
.tv-mark {{
  width: 32px; height: 32px; border-radius: 6px;
  background: {c['elevated']}; border: 1px solid {c['border']};
  display: flex; align-items: center; justify-content: center;
  color: {c['accent']}; font-size: 14px; font-weight: 600;
}}
.tv-brand strong {{ display: block; font-size: 15px; font-weight: 600; }}
.tv-brand span {{ display: block; font-size: 12px; color: {c['dim']}; font-weight: 400; margin-top: 2px; }}
.tv-nav-label {{
  font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
  color: {c['dim']}; padding: 4px 8px 6px;
}}
.tv-side-foot {{
  margin-top: 18px; padding: 10px 8px 0; border-top: 1px solid {c['border']};
  font-size: 12px; color: {c['muted']}; line-height: 1.55;
}}
.tv-page {{
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px; margin-bottom: 16px;
}}
.tv-page h1 {{
  margin: 0; font-size: 26px; font-weight: 600; letter-spacing: -0.02em;
}}
.tv-page p {{ margin: 4px 0 0; font-size: 14px; color: {c['muted']}; }}
.tv-page-meta {{ text-align: right; font-size: 13px; color: {c['muted']}; }}
.tv-status {{ display: inline-flex; align-items: center; gap: 7px; color: {c['green']}; }}
.tv-dot {{ width: 6px; height: 6px; border-radius: 50%; background: {c['green']}; }}

.tv-card {{
  background: {c['surface']}; border: 1px solid {c['border']};
  border-radius: {RADIUS}; padding: 14px 16px;
}}
.tv-card-title {{
  font-size: 13px; font-weight: 600; color: {c['muted']}; margin: 0 0 10px;
}}
.tv-section {{ font-size: 13px; font-weight: 600; color: {c['muted']}; margin: 16px 0 8px; }}
.tv-muted {{ color: {c['muted']}; font-size: 13px; line-height: 1.5; }}
.tv-dim {{ color: {c['dim']}; font-size: 12px; }}
.tv-label {{ font-size: 16px; font-weight: 600; }}
.tv-value {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 32px; font-weight: 500; line-height: 1;
}}
.tv-bar {{ height: 4px; background: {c['elevated']}; margin-top: 8px; width: 100%; border-radius: 2px; overflow: hidden; }}
.tv-bar i {{ display: block; height: 100%; background: {c['accent']}; }}
.tv-row {{
  display: flex; justify-content: space-between; gap: 16px;
  font-size: 14px; padding: 7px 0; border-bottom: 1px solid {c['border']};
}}
.tv-row:last-child {{ border-bottom: 0; }}
.tv-row span:first-child {{ color: {c['muted']}; }}
.tv-footer {{
  margin-top: 24px; padding-top: 10px; border-top: 1px solid {c['border']};
  color: {c['dim']}; font-size: 12px;
}}
.tv-wave {{ height: 64px; display: flex; align-items: flex-end; gap: 2px; }}
.tv-wave i {{ width: 3px; background: {c['accent']}; opacity: 0.75; display: block; border-radius: 1px; }}
.tv-wave.live i {{ animation: tvPulse 1.2s ease-in-out infinite; }}
.tv-wave.live i:nth-child(odd) {{ animation-delay: 0.15s; }}
@keyframes tvPulse {{ 0%,100% {{ opacity: 0.35; }} 50% {{ opacity: 1; }} }}

.tv-decision {{ display: flex; gap: 16px; align-items: center; }}
.tv-decision-risk {{ font-size: 18px; font-weight: 600; }}
.tv-decision-action {{ font-size: 14px; color: {c['muted']}; margin-top: 4px; }}
.tv-note {{ font-size: 13px; color: {c['muted']}; margin-top: 8px; }}
.tv-ring {{
  width: 56px; height: 56px; flex-shrink: 0; border-radius: 50%;
  border: 5px solid {c['border']};
}}
.tv-ring.ok {{ border-color: {c['green']}; }}
.tv-ring.warn {{ border-color: {c['amber']}; }}
.tv-ring.crit {{ border-color: {c['red']}; }}
.tv-ring.idle {{ border-color: {c['border']}; }}

.tv-signals {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }}
.tv-signal {{
  background: {c['surface']}; border: 1px solid {c['border']};
  border-radius: {RADIUS}; padding: 12px;
}}
.tv-signal .name {{ font-size: 12px; color: {c['muted']}; margin-bottom: 6px; }}
.tv-signal .val {{ font-size: 14px; font-weight: 600; }}

.tv-timeline {{ padding: 0; }}
.tv-utt {{
  display: grid; grid-template-columns: 56px 1fr auto; gap: 10px; align-items: start;
  padding: 9px 0; border-bottom: 1px solid {c['border']}; font-size: 14px;
}}
.tv-utt:last-child {{ border-bottom: 0; }}
.tv-utt .who {{ font-size: 12px; color: {c['dim']}; }}
.tv-utt .said {{ line-height: 1.45; }}
.tv-tag {{
  font-size: 11px; color: {c['muted']}; border: 1px solid {c['border']};
  padding: 1px 6px; border-radius: 3px; margin-left: 4px; white-space: nowrap;
}}
.tv-tag.warn {{ color: {c['amber']}; border-color: {c['amber']}; }}
.tv-tag.crit {{ color: {c['red']}; border-color: {c['red']}; }}

.tv-why ul {{ margin: 0; padding: 0; }}
.tv-why li {{
  list-style: none; font-size: 14px; line-height: 1.45;
  padding: 5px 0 5px 12px; position: relative;
}}
.tv-why li:before {{
  content: ""; position: absolute; left: 0; top: 11px;
  width: 5px; height: 5px; border-radius: 50%; background: {c['dim']};
}}

.tv-handshake {{
  border: 1px solid {c['border']}; border-left: 3px solid {c['red']};
  background: {c['surface']}; border-radius: {RADIUS}; padding: 14px 16px;
}}
.tv-handshake h3 {{ margin: 0; font-size: 16px; font-weight: 600; color: {c['red']}; }}

.tv-trail {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 18px; margin: 6px 0 4px;
}}
.tv-trail span {{ color: {c['muted']}; font-size: 13px; }}
.tv-choice {{
  background: {c['surface']}; border: 1px solid {c['border']};
  border-radius: {RADIUS}; padding: 12px;
}}
.tv-choice.active {{ border-color: {c['accent']}; }}
.tv-choice .id {{ font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 13px; color: {c['dim']}; }}
.tv-choice .title {{ font-size: 16px; font-weight: 600; margin-top: 4px; }}
.tv-choice .sub {{ font-size: 13px; color: {c['muted']}; margin-top: 2px; }}

.tv-pipe {{
  display: flex; gap: 0; align-items: stretch; overflow-x: auto;
}}
.tv-stage {{
  flex: 1; min-width: 88px; text-align: center; padding: 8px 6px;
  border: 1px solid {c['border']}; background: {c['surface2']};
}}
.tv-stage:first-child {{ border-radius: 6px 0 0 6px; }}
.tv-stage:last-child {{ border-radius: 0 6px 6px 0; }}
.tv-stage .nm {{ font-size: 12px; font-weight: 600; }}
.tv-stage .st {{ font-size: 11px; color: {c['dim']}; margin-top: 3px; }}
.tv-stage.done {{ border-color: {c['green']}; }}
.tv-stage.done .st {{ color: {c['green']}; }}
.tv-stage.run {{ border-color: {c['accent']}; }}
.tv-stage.run .st {{ color: {c['accent']}; }}
.tv-stage.fail {{ border-color: {c['amber']}; }}

.tv-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.tv-table th, .tv-table td {{
  text-align: left; padding: 8px 10px 8px 0;
  border-bottom: 1px solid {c['border']}; vertical-align: top;
}}
.tv-table th {{ color: {c['muted']}; font-weight: 500; font-size: 13px; }}
.tv-table td.num {{
  font-family: "IBM Plex Mono", ui-monospace, monospace; text-align: right;
}}
.tv-report h2 {{ font-size: 13px; font-weight: 600; color: {c['muted']}; margin: 16px 0 6px; }}
.tv-report p {{ font-size: 14px; line-height: 1.5; margin: 0 0 6px; }}
.tv-banner {{ font-size: 13px; color: {c['muted']}; margin: 0 0 12px; }}

.tv-upload-hint {{ font-size: 13px; color: {c['dim']}; margin: 4px 0 10px; line-height: 1.45; }}
.tv-split {{ display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 12px; }}
@media (max-width: 1100px) {{
  .tv-signals {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .tv-utt {{ grid-template-columns: 48px 1fr; }}
  .tv-split {{ grid-template-columns: 1fr; }}
  .tv-pipe {{ flex-wrap: wrap; }}
  .tv-stage:first-child, .tv-stage:last-child {{ border-radius: 6px; }}
}}
@media (max-width: 900px) {{
  .tv-decision {{ flex-direction: column; align-items: flex-start; }}
  .tv-page {{ flex-direction: column; }}
}}
@media print {{
  [data-testid="stSidebar"], .tv-page, .stButton, .tv-footer {{ display: none !important; }}
}}
</style>
"""
