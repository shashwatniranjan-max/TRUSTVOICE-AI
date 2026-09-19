"""Restrained enterprise console theme for TRUSTVOICE AI."""

COLORS = {
    "bg": "#0e1013",
    "bg2": "#13161b",
    "surface": "#181c22",
    "surface2": "#1c2128",
    "border": "#2a3038",
    "text": "#dce0e6",
    "muted": "#8b919b",
    "accent": "#4a7ec8",
    "green": "#6aa37a",
    "amber": "#c4a35a",
    "red": "#c45c5c",
    "gray": "#6d737c",
}

SPACING = {"xs": "4px", "sm": "8px", "md": "12px", "lg": "16px", "xl": "24px"}
RADIUS = "3px"
FONT = '"IBM Plex Sans", "Segoe UI", sans-serif'

STATUS_COLOR = {
    "LOW": COLORS["green"],
    "CONTINUE": COLORS["green"],
    "LIKELY AUTHENTIC": COLORS["green"],
    "GOOD": COLORS["green"],
    "ELEVATED": COLORS["amber"],
    "WARN": COLORS["amber"],
    "INCONCLUSIVE": COLORS["amber"],
    "INCONCLUSIVE / AUDIO QUALITY": COLORS["amber"],
    "MEDIUM": COLORS["amber"],
    "HIGH": COLORS["red"],
    "CRITICAL": COLORS["red"],
    "VERIFY": COLORS["red"],
    "CRITICAL INTERVENTION": COLORS["red"],
    "LIKELY SPOOF": COLORS["red"],
    "UNAVAILABLE": COLORS["gray"],
    "NOT_AVAILABLE": COLORS["gray"],
    "UNVERIFIED": COLORS["gray"],
    "VERIFIED": COLORS["green"],
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
}}
[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{
  max-width: 1180px;
  padding: 0.55rem 1.4rem 1.8rem;
}}
[data-testid="stSidebar"] {{
  background: {c['bg2']};
  border-right: 1px solid {c['border']};
}}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
  padding: 1rem 0.7rem 1.2rem;
}}
[data-testid="stSidebar"] .stButton {{ margin-bottom: 2px; }}
[data-testid="stSidebar"] .stButton > button {{
  min-height: 32px !important;
  height: 32px !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  justify-content: flex-start !important;
  padding: 0 10px !important;
  background: transparent !important;
  color: {c['muted']} !important;
  border: 0 !important;
  border-left: 2px solid transparent !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
  background: {c['surface']} !important;
  color: {c['text']} !important;
  border-color: transparent !important;
}}
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {{
  background: {c['surface']} !important;
  color: {c['text']} !important;
  border-left: 2px solid {c['accent']} !important;
}}
.stButton > button {{
  border-radius: {RADIUS} !important;
  border: 1px solid {c['border']} !important;
  background: {c['surface']} !important;
  color: {c['text']} !important;
  min-height: 34px !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  box-shadow: none !important;
}}
.stButton > button:hover {{
  border-color: {c['accent']} !important;
}}
button[kind="primary"], button[data-testid="baseButton-primary"] {{
  border-color: {c['accent']} !important;
  color: {c['text']} !important;
}}
[data-testid="stFileUploader"] {{
  border: 1px dashed {c['border']};
  border-radius: {RADIUS};
  background: transparent;
}}
.stProgress > div > div > div > div {{ background: {c['accent']}; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: {c['muted']} !important; }}
div[data-testid="stAlert"] {{
  background: {c['surface']} !important;
  border: 1px solid {c['border']} !important;
  color: {c['text']} !important;
}}
.stExpander {{
  border: 1px solid {c['border']} !important;
  border-radius: {RADIUS} !important;
  background: transparent !important;
}}

.tv-brand {{
  font-size: 13px; font-weight: 600; letter-spacing: 0.02em;
  padding: 2px 8px 14px; color: {c['text']};
}}
.tv-brand span {{
  display: block; font-size: 11px; color: {c['muted']};
  font-weight: 400; margin-top: 3px; letter-spacing: 0;
}}
.tv-top {{
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 16px; padding: 2px 0 10px; margin-bottom: 14px;
  border-bottom: 1px solid {c['border']};
}}
.tv-top-title {{ font-size: 14px; font-weight: 600; }}
.tv-top-title span {{
  display: block; font-size: 12px; color: {c['muted']}; font-weight: 400; margin-top: 2px;
}}
.tv-top-meta {{
  display: flex; align-items: center; gap: 16px;
  font-size: 12px; color: {c['muted']}; white-space: nowrap;
}}
.tv-status {{ display: flex; align-items: center; gap: 7px; color: {c['green']}; }}
.tv-dot {{
  width: 6px; height: 6px; border-radius: 50%; background: {c['green']};
}}
.tv-section {{
  font-size: 12px; font-weight: 600; color: {c['muted']};
  margin: 18px 0 8px;
}}
.tv-muted {{ color: {c['muted']}; font-size: 12px; line-height: 1.5; }}
.tv-label {{ font-size: 14px; font-weight: 600; }}
.tv-value {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 32px; font-weight: 500; line-height: 1;
}}
.tv-value small, .tv-value .tv-muted {{ font-size: 13px; font-weight: 400; }}
.tv-bar {{
  height: 3px; background: {c['surface2']}; margin-top: 6px; width: 100%;
}}
.tv-bar i {{ display: block; height: 100%; background: {c['accent']}; }}
.tv-row {{
  display: flex; justify-content: space-between; gap: 16px;
  font-size: 13px; padding: 7px 0; border-bottom: 1px solid {c['border']};
}}
.tv-row:last-child {{ border-bottom: 0; }}
.tv-row span:first-child {{ color: {c['muted']}; }}
.tv-footer {{
  margin-top: 28px; padding-top: 10px; border-top: 1px solid {c['border']};
  color: {c['muted']}; font-size: 11px;
}}
.tv-wave {{ height: 56px; display: flex; align-items: flex-end; gap: 2px; }}
.tv-wave i {{ width: 2px; background: {c['accent']}; opacity: 0.7; display: block; }}

.tv-decision {{
  display: grid; grid-template-columns: 160px 1fr; gap: 20px;
  padding: 4px 0 6px; align-items: end;
}}
.tv-decision-risk {{ font-size: 18px; font-weight: 600; line-height: 1.2; }}
.tv-decision-action {{ font-size: 13px; color: {c['muted']}; margin-top: 4px; }}
.tv-note {{ font-size: 12px; color: {c['muted']}; margin-top: 8px; }}

.tv-signals {{
  display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 18px;
  padding: 4px 0 2px;
}}
.tv-signal .name {{ font-size: 11px; color: {c['muted']}; margin-bottom: 4px; }}
.tv-signal .val {{ font-size: 13px; font-weight: 500; }}

.tv-timeline {{ padding: 2px 0; }}
.tv-utt {{
  display: grid; grid-template-columns: 72px 1fr; gap: 12px;
  padding: 8px 0; border-bottom: 1px solid {c['border']};
}}
.tv-utt:last-child {{ border-bottom: 0; }}
.tv-utt .who {{ font-size: 11px; color: {c['muted']}; padding-top: 2px; }}
.tv-utt .said {{ font-size: 14px; line-height: 1.45; }}
.tv-utt .step {{ font-size: 10px; color: {c['gray']}; display: block; margin-bottom: 2px; }}

.tv-why {{ padding: 2px 0; }}
.tv-why li {{
  list-style: none; font-size: 13px; line-height: 1.45;
  padding: 5px 0 5px 12px; position: relative; color: {c['text']};
}}
.tv-why li:before {{
  content: ""; position: absolute; left: 0; top: 11px;
  width: 5px; height: 5px; border-radius: 50%; background: {c['muted']};
}}
.tv-why ul {{ margin: 0; padding: 0; }}

.tv-handshake {{
  border-left: 3px solid {c['red']}; padding: 8px 0 8px 14px; margin: 8px 0 10px;
}}
.tv-handshake h3 {{
  margin: 0; font-size: 14px; font-weight: 600; color: {c['red']};
}}

.tv-trail {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 18px; letter-spacing: 0.02em; margin: 6px 0 4px;
}}
.tv-trail span {{ color: {c['muted']}; font-size: 13px; }}

.tv-choice {{
  padding: 8px 0 10px; border-bottom: 1px solid {c['border']};
}}
.tv-choice.active {{ border-bottom-color: {c['accent']}; }}
.tv-choice .id {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 12px; color: {c['muted']};
}}
.tv-choice .title {{ font-size: 14px; font-weight: 600; margin-top: 2px; }}
.tv-choice .sub {{ font-size: 12px; color: {c['muted']}; margin-top: 2px; }}

.tv-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.tv-table th, .tv-table td {{
  text-align: left; padding: 8px 10px 8px 0;
  border-bottom: 1px solid {c['border']}; vertical-align: top;
}}
.tv-table th {{ color: {c['muted']}; font-weight: 500; font-size: 12px; }}
.tv-table td.num {{
  font-family: "IBM Plex Mono", ui-monospace, monospace; text-align: right;
}}

.tv-report h2 {{
  font-size: 13px; font-weight: 600; color: {c['muted']};
  margin: 16px 0 6px; padding: 0;
}}
.tv-report p {{ font-size: 13px; line-height: 1.5; margin: 0 0 6px; }}

.tv-banner {{
  font-size: 12px; color: {c['muted']}; margin: 0 0 12px;
}}

@media (max-width: 900px) {{
  .tv-decision {{ grid-template-columns: 1fr; }}
  .tv-signals {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .tv-top {{ flex-wrap: wrap; }}
}}
@media print {{
  [data-testid="stSidebar"], .tv-top, .stButton, .tv-footer {{ display: none !important; }}
  html, body, [data-testid="stAppViewContainer"] {{ background: #fff !important; color: #111 !important; }}
}}
</style>
"""
