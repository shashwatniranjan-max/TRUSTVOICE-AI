"""Single SOC-style design system for TRUSTVOICE AI."""

COLORS = {
    "bg": "#0b0d10",
    "bg2": "#10141a",
    "surface": "#151a21",
    "surface2": "#1b212a",
    "border": "#2a313c",
    "text": "#e6e9ee",
    "muted": "#8b939e",
    "accent": "#3d8bfd",
    "green": "#3dd68c",
    "amber": "#e8b339",
    "red": "#f07178",
    "gray": "#6b7380",
}

SPACING = {"xs": "4px", "sm": "8px", "md": "12px", "lg": "18px", "xl": "24px"}
RADIUS = "4px"
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


def css() -> str:
    c = COLORS
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');
html, body, [data-testid="stAppViewContainer"] {{
  background: {c['bg']};
  color: {c['text']};
  font-family: {FONT};
}}
[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ max-width: 1280px; padding: 0.9rem 1.2rem 2.4rem; }}
[data-testid="stSidebar"] {{
  background: {c['bg2']};
  border-right: 1px solid {c['border']};
}}
[data-testid="stSidebar"] .block-container {{ padding: 1rem 0.75rem; }}
.stButton > button {{
  width: 100%;
  border-radius: {RADIUS} !important;
  border: 1px solid {c['border']} !important;
  background: {c['surface']} !important;
  color: {c['text']} !important;
  min-height: 38px !important;
  font-weight: 600 !important;
  font-size: 13px !important;
}}
.stButton > button:hover {{
  border-color: {c['accent']} !important;
}}
[data-testid="stFileUploader"] {{
  border: 1px dashed {c['border']};
  border-radius: {RADIUS};
  background: {c['surface']};
}}
.stProgress > div > div > div > div {{ background: {c['accent']}; }}
.tv-top {{
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid {c['border']}; padding: 0 0 12px; margin-bottom: 16px;
}}
.tv-brand {{ font-size: 15px; font-weight: 700; letter-spacing: 0.04em; }}
.tv-brand span {{ display: block; font-size: 11px; color: {c['muted']}; font-weight: 500; letter-spacing: 0.02em; margin-top: 2px; }}
.tv-status {{ font-size: 12px; color: {c['green']}; display: flex; align-items: center; gap: 8px; }}
.tv-dot {{ width: 7px; height: 7px; border-radius: 50%; background: {c['green']}; }}
.tv-meta {{ font-size: 12px; color: {c['muted']}; text-align: right; }}
.tv-section {{
  font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
  color: {c['muted']}; margin: 18px 0 8px; border-bottom: 1px solid {c['border']}; padding-bottom: 6px;
}}
.tv-panel {{
  background: {c['surface']}; border: 1px solid {c['border']}; border-radius: {RADIUS};
  padding: 14px 16px;
}}
.tv-kicker {{ font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: {c['muted']}; }}
.tv-value {{ font-family: "IBM Plex Mono", monospace; font-size: 28px; font-weight: 500; line-height: 1.1; }}
.tv-value.small {{ font-size: 18px; }}
.tv-label {{ font-size: 13px; font-weight: 600; margin-top: 4px; }}
.tv-muted {{ color: {c['muted']}; font-size: 12px; line-height: 1.55; }}
.tv-bar {{ height: 6px; background: {c['surface2']}; border: 1px solid {c['border']}; margin-top: 6px; }}
.tv-bar i {{ display: block; height: 100%; background: {c['accent']}; }}
.tv-row {{ display: flex; justify-content: space-between; gap: 12px; font-size: 12px; padding: 6px 0;
  border-bottom: 1px solid {c['border']}; }}
.tv-row:last-child {{ border-bottom: 0; }}
.tv-row span:first-child {{ color: {c['muted']}; }}
.tv-wave {{ height: 88px; display: flex; align-items: center; gap: 2px; }}
.tv-wave i {{ width: 3px; background: {c['accent']}; opacity: 0.85; display: block; }}
.tv-alert {{ border: 1px solid {c['red']}; background: {c['surface2']}; padding: 12px 14px; border-radius: {RADIUS}; }}
.tv-footer {{ margin-top: 28px; padding-top: 10px; border-top: 1px solid {c['border']};
  color: {c['muted']}; font-size: 11px; }}
.tv-tag {{ font-size: 11px; color: {c['muted']}; border: 1px solid {c['border']}; padding: 2px 6px; }}
</style>
"""
