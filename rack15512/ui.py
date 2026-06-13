"""Premium UI theme and components for the Racks & Rollers app.

A single CSS system driven by CSS variables so the light / dark toggle only
swaps a handful of values.  Helper functions render the elegant pieces
(hero band, cards, status pills, metric tiles) as HTML; interactive widgets
stay native Streamlit but are restyled by the same CSS.
"""

from __future__ import annotations

import html as _html

import streamlit as st

from . import branding as B

# ---- palette ---------------------------------------------------------------
_LIGHT = {
    "bg": "#EEF3F4", "bg2": "#E2EBEC",
    "surface": "#FFFFFF", "surface2": "#F4F8F8",
    "text": "#16282C", "muted": "#5E7176", "border": "#DCE6E7",
    "teal": "#0C8490", "teal2": "#12A6B4", "grey": "#545454",
    "shadow": "0 6px 24px rgba(12,132,144,.10)",
    "shadow_hi": "0 12px 34px rgba(12,132,144,.18)",
    "sidebar": "#0E2A2E", "sidebar_text": "#E7F2F2",
}
_DARK = {
    "bg": "#0C1315", "bg2": "#0A1012",
    "surface": "#162024", "surface2": "#1C282C",
    "text": "#E8EFF0", "muted": "#9AB0B4", "border": "#26343A",
    "teal": "#21B3C2", "teal2": "#37C7D6", "grey": "#C7D2D4",
    "shadow": "0 8px 28px rgba(0,0,0,.45)",
    "shadow_hi": "0 14px 40px rgba(0,0,0,.55)",
    "sidebar": "#0A1416", "sidebar_text": "#DCEAEC",
}


def is_dark() -> bool:
    return bool(st.session_state.get("dark_mode", False))


def apply_theme() -> None:
    """Inject the full theme (call once at the top of the app)."""
    v = _DARK if is_dark() else _LIGHT
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap');
:root {{
  --bg:{v['bg']}; --bg2:{v['bg2']}; --surface:{v['surface']};
  --surface2:{v['surface2']}; --text:{v['text']}; --muted:{v['muted']};
  --border:{v['border']}; --teal:{v['teal']}; --teal2:{v['teal2']};
  --grey:{v['grey']}; --shadow:{v['shadow']}; --shadow-hi:{v['shadow_hi']};
}}
html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {{
  font-family:'Manrope',-apple-system,Segoe UI,Roboto,sans-serif;
}}
.stApp, [data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(1200px 600px at 100% -10%, {v['teal']}14, transparent 60%),
    radial-gradient(900px 500px at -10% 110%, {v['teal2']}10, transparent 55%),
    var(--bg);
  color:var(--text);
}}
[data-testid="stMain"] .block-container {{
  padding-top:2.2rem; padding-bottom:4rem; max-width:1280px;
  animation:fade .5s ease;
}}
@keyframes fade {{ from {{opacity:0; transform:translateY(6px)}}
                   to {{opacity:1; transform:none}} }}
h1,h2,h3,h4 {{ color:var(--text); letter-spacing:-.02em; font-weight:800; }}
p, span, label, .stMarkdown {{ color:var(--text); }}
hr {{ border-color:var(--border); }}

/* sidebar */
[data-testid="stSidebar"] {{
  background:linear-gradient(180deg,{v['sidebar']},{v['bg2']});
  border-right:1px solid var(--border);
}}
[data-testid="stSidebar"] * {{ color:{v['sidebar_text']}; }}
[data-testid="stSidebar"] .stButton>button {{
  background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12);
  color:{v['sidebar_text']}; font-weight:600; border-radius:12px;
  transition:.18s;
}}
[data-testid="stSidebar"] .stButton>button:hover {{
  background:{v['teal']}; border-color:{v['teal']}; color:#fff;
  transform:translateY(-1px);
}}

/* buttons */
.stButton>button, .stDownloadButton>button {{
  border-radius:12px; font-weight:600; padding:.5rem 1rem;
  border:1px solid var(--border); background:var(--surface);
  color:var(--text); transition:.18s ease; box-shadow:0 1px 2px rgba(0,0,0,.04);
}}
.stButton>button:hover, .stDownloadButton>button:hover {{
  border-color:{v['teal']}; color:{v['teal']};
  transform:translateY(-1px); box-shadow:var(--shadow);
}}
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {{
  background:linear-gradient(135deg,{v['teal']},{v['teal2']});
  color:#fff; border:none; box-shadow:0 6px 18px {v['teal']}55;
}}
.stButton>button[kind="primary"]:hover {{
  filter:brightness(1.06); transform:translateY(-2px);
  box-shadow:0 10px 26px {v['teal']}66; color:#fff;
}}

/* cards = bordered containers */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background:var(--surface); border:1px solid var(--border)!important;
  border-radius:18px; box-shadow:var(--shadow); padding:4px;
  transition:.2s ease;
}}
[data-testid="stVerticalBlockBorderWrapper"]:hover {{
  box-shadow:var(--shadow-hi); transform:translateY(-2px);
  border-color:{v['teal']}66!important;
}}

/* inputs */
[data-baseweb="input"], [data-baseweb="select"]>div,
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
textarea {{
  border-radius:10px!important;
}}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {{
  background:var(--surface2); color:var(--text);
}}

/* metrics */
[data-testid="stMetric"] {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:16px; padding:14px 16px; box-shadow:var(--shadow);
}}
[data-testid="stMetricValue"] {{ color:{v['teal']}; font-weight:800; }}
[data-testid="stMetricLabel"] {{ color:var(--muted); }}

/* tabs */
[data-baseweb="tab-list"] {{ gap:6px; border-bottom:1px solid var(--border); }}
[data-baseweb="tab"] {{
  background:transparent; border-radius:10px 10px 0 0; font-weight:600;
  color:var(--muted); padding:8px 16px;
}}
[data-baseweb="tab"][aria-selected="true"] {{
  color:{v['teal']}; background:var(--surface);
  border-bottom:2px solid {v['teal']};
}}
[data-testid="stDataFrame"] {{ border-radius:12px; overflow:hidden; }}
[data-testid="stExpander"] {{
  border:1px solid var(--border); border-radius:14px; background:var(--surface);
}}

/* premium building blocks */
.rnr-hero {{
  position:relative; border-radius:22px; padding:26px 30px; margin-bottom:22px;
  background:linear-gradient(120deg,{v['teal']},{v['teal2']} 60%, {v['teal']});
  color:#fff; box-shadow:0 14px 40px {v['teal']}44; overflow:hidden;
}}
.rnr-hero::after {{
  content:""; position:absolute; right:-40px; top:-60px; width:240px;
  height:240px; border-radius:50%; background:rgba(255,255,255,.10);
}}
.rnr-hero .eyebrow {{ font-size:.74rem; letter-spacing:.18em;
  text-transform:uppercase; opacity:.85; font-weight:700; }}
.rnr-hero h1 {{ color:#fff; margin:.1rem 0 .2rem; font-size:2rem; }}
.rnr-hero .sub {{ opacity:.92; font-size:.98rem; }}
.rnr-pill {{ display:inline-flex; align-items:center; gap:6px;
  padding:4px 12px; border-radius:999px; font-weight:700; font-size:.8rem; }}
.rnr-pill.pass {{ background:{v['teal']}1f; color:{v['teal']};
  border:1px solid {v['teal']}55; }}
.rnr-pill.fail {{ background:#e5393522; color:#e35335;
  border:1px solid #e3533566; }}
.rnr-pill.idle {{ background:var(--surface2); color:var(--muted);
  border:1px solid var(--border); }}
.rnr-dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
.rnr-tile {{ background:var(--surface); border:1px solid var(--border);
  border-radius:16px; padding:14px 18px; box-shadow:var(--shadow); }}
.rnr-tile .k {{ color:var(--muted); font-size:.78rem; font-weight:600;
  text-transform:uppercase; letter-spacing:.06em; }}
.rnr-tile .v {{ color:{v['teal']}; font-size:1.5rem; font-weight:800; }}
.rnr-chiprow {{ display:flex; gap:8px; flex-wrap:wrap; }}
.rnr-muted {{ color:var(--muted); }}
#MainMenu, footer, [data-testid="stToolbar"] {{ visibility:hidden; }}
</style>""", unsafe_allow_html=True)


def hero(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    eb = (f'<div class="eyebrow">{_html.escape(eyebrow)}</div>'
          if eyebrow else "")
    sub = f'<div class="sub">{_html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(f'<div class="rnr-hero">{eb}<h1>{_html.escape(title)}</h1>'
                f'{sub}</div>', unsafe_allow_html=True)


def pill(verdict: str) -> str:
    v = (verdict or "not run").upper()
    cls = "pass" if v == "PASS" else "fail" if v == "FAIL" else "idle"
    return (f'<span class="rnr-pill {cls}"><span class="rnr-dot" '
            f'style="background:currentColor"></span>{_html.escape(v)}</span>')


def tile(label: str, value: str) -> str:
    return (f'<div class="rnr-tile"><div class="k">{_html.escape(label)}</div>'
            f'<div class="v">{_html.escape(str(value))}</div></div>')


def theme_toggle() -> None:
    st.toggle("🌙 Dark mode", key="dark_mode")
