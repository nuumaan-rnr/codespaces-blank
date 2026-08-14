"""Premium UI theme and components for the Racks & Rollers app.

A single CSS system driven by CSS variables so the light / dark toggle only
swaps a handful of values.  Helper functions render the elegant pieces
(hero band, cards, status pills, metric tiles) as HTML; interactive widgets
stay native Streamlit but are restyled by the same CSS.
"""

from __future__ import annotations

import html as _html
import json as _json
import os as _os
import sys as _sys
import time as _time

import streamlit as st

from . import branding as B

_PREF = ".rnr_settings.json"


def load_dark_pref() -> bool:
    try:
        with open(_PREF, encoding="utf-8") as f:
            return bool(_json.load(f).get("dark_mode", False))
    except Exception:
        return False


def _save_dark_pref(value: bool) -> None:
    try:
        with open(_PREF, "w", encoding="utf-8") as f:
            _json.dump({"dark_mode": bool(value)}, f)
    except Exception:
        pass

# ---- palette (Vercel-clean: crisp surfaces, thin borders) ------------------
_LIGHT = {
    "bg": "#FFFFFF", "bg2": "#FAFAFA",
    "surface": "#FFFFFF", "surface2": "#FAFAFA",
    "text": "#111111", "muted": "#666666", "border": "#EAEAEA",
    "teal": "#0C8490", "teal2": "#12A6B4", "grey": "#545454",
    "shadow": "0 1px 2px rgba(0,0,0,.05)",
    "shadow_hi": "0 6px 20px rgba(0,0,0,.10)",
    "sidebar": "#0B0B0C", "sidebar_text": "#EDEDED",
}
_DARK = {
    "bg": "#000000", "bg2": "#0A0A0A",
    "surface": "#0A0A0A", "surface2": "#111111",
    "text": "#EDEDED", "muted": "#8A8A8A", "border": "#262626",
    "teal": "#22B8C6", "teal2": "#3AD0DE", "grey": "#C7D2D4",
    "shadow": "0 1px 2px rgba(0,0,0,.6)",
    "shadow_hi": "0 8px 28px rgba(0,0,0,.6)",
    "sidebar": "#000000", "sidebar_text": "#EDEDED",
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
  /* one radius scale, used everywhere below instead of ad-hoc values */
  --r-sm:8px; --r-md:12px; --r-lg:16px; --r-pill:999px;
  /* sidebar text always sits on a near-black surface (both themes) - a
     fixed, contrast-checked tone for secondary sidebar text (>=4.5:1 on
     black) instead of opacity, which can silently drop below AA */
  --sidebar-muted:rgba(237,237,237,.72);
}}
html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {{
  font-family:'Manrope',-apple-system,Segoe UI,Roboto,sans-serif;
}}
.stApp, [data-testid="stAppViewContainer"] {{
  background:var(--bg); color:var(--text);
}}
[data-testid="stHeader"] {{ background:transparent; z-index:1000000; }}
/* keep the sidebar expand control visible + clickable after collapsing
   (covers the several test-ids Streamlit has used across versions) */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stExpandSidebarButton"],
[data-testid="baseButton-headerNoPadding"] {{
  display:flex !important; visibility:visible !important; opacity:1 !important;
  z-index:1000002 !important; color:var(--text) !important;
  background:var(--surface) !important; border:1px solid var(--border);
  border-radius:var(--r-sm);
}}
[data-testid="stMain"] .block-container {{
  padding-top:2.2rem; padding-bottom:170px; max-width:1280px;
  animation:fade .5s ease;
}}
@keyframes fade {{ from {{opacity:0; transform:translateY(6px)}}
                   to {{opacity:1; transform:none}} }}
h1,h2,h3,h4 {{ color:var(--text); letter-spacing:-.02em; font-weight:800; }}
p, span, label, .stMarkdown {{ color:var(--text); }}
hr {{ border-color:var(--border); }}

/* sidebar - a compact, app-like nav: left-aligned pills, a filled "active"
   state for the current section, and grouped-by-whitespace (not lines)  */
[data-testid="stSidebar"] {{
  background:linear-gradient(180deg,{v['sidebar']},{v['bg2']});
  border-right:1px solid var(--border);
}}
[data-testid="stSidebar"] * {{ color:{v['sidebar_text']}; }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap:.4rem; }}
[data-testid="stSidebar"] hr {{
  margin:14px 0; border-color:rgba(255,255,255,.10);
}}
[data-testid="stSidebar"] .stButton>button {{
  background:transparent; border:1px solid transparent;
  color:{v['sidebar_text']}; font-weight:600; border-radius:var(--r-md);
  transition:.14s ease; justify-content:flex-start; gap:8px;
  padding:.5rem .7rem; box-shadow:none;
}}
[data-testid="stSidebar"] .stButton>button p {{ text-align:left; }}
[data-testid="stSidebar"] .stButton>button:hover {{
  background:rgba(255,255,255,.08); border-color:rgba(255,255,255,.10);
  color:#fff; transform:none;
}}
[data-testid="stSidebar"] .stButton>button[kind="primary"] {{
  background:{v['teal']}; border-color:{v['teal']}; color:#fff;
  box-shadow:0 2px 12px {v['teal']}4d;
}}
[data-testid="stSidebar"] .stButton>button[kind="primary"]:hover {{
  background:{v['teal2']}; border-color:{v['teal2']};
}}
[data-testid="stSidebar"] .stToggle {{ margin:2px 0 4px; }}
.rnr-sb-brand {{ display:flex; align-items:center; gap:10px; padding:2px 0 4px; }}
.rnr-sb-brand .name {{ font-weight:800; font-size:1rem; letter-spacing:-.01em; }}
.rnr-sb-brand .tag {{ font-size:.72rem; color:var(--sidebar-muted); margin-top:1px; }}
.rnr-sbchip {{ background:rgba(255,255,255,.05); border:1px solid
  rgba(255,255,255,.10); border-radius:var(--r-sm); padding:8px 12px;
  margin:2px 0; }}
.rnr-sbchip .k {{ font-size:.64rem; text-transform:uppercase;
  letter-spacing:.07em; color:var(--sidebar-muted); font-weight:700; }}
.rnr-sbchip .v {{ font-size:.85rem; font-weight:700; margin-top:2px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.rnr-profile {{ display:flex; align-items:center; gap:10px; padding:4px 0; }}
.rnr-profile .av {{ width:32px; height:32px; border-radius:var(--r-pill);
  background:{v['teal']}; color:#fff; display:flex; align-items:center;
  justify-content:center; font-weight:800; font-size:.9rem; flex:none; }}
.rnr-profile .meta {{ min-width:0; }}
.rnr-profile .nm {{ font-weight:700; font-size:.86rem; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap; }}
.rnr-profile .un {{ font-size:.72rem; color:var(--sidebar-muted); margin-left:5px; }}
.rnr-sbfooter {{ font-size:.7rem; line-height:1.8; color:var(--sidebar-muted);
  margin-top:2px; }}
.rnr-sbfooter a {{ color:inherit; }}

/* buttons - nowrap so a narrow column (e.g. a compact list's action column)
   never wraps a short label onto two lines and inflates the row height */
.stButton>button, .stDownloadButton>button {{
  border-radius:var(--r-md); font-weight:600; padding:.5rem 1rem;
  border:1px solid var(--border); background:var(--surface);
  color:var(--text); transition:.18s ease; box-shadow:0 1px 2px rgba(0,0,0,.04);
  white-space:nowrap;
}}
.stButton>button:hover, .stDownloadButton>button:hover {{
  border-color:{v['teal']}; color:{v['teal']};
  transform:translateY(-1px); box-shadow:var(--shadow);
}}
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {{
  background:{v['teal']}; color:#fff; border:1px solid {v['teal']};
  box-shadow:none;
}}
.stButton>button[kind="primary"]:hover {{
  background:{v['teal2']}; border-color:{v['teal2']};
  transform:translateY(-1px); color:#fff;
}}

/* cards = bordered containers */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background:var(--surface); border:1px solid var(--border)!important;
  border-radius:var(--r-md); box-shadow:var(--shadow); padding:8px;
  transition:.16s ease;
}}
[data-testid="stVerticalBlockBorderWrapper"]:hover {{
  box-shadow:var(--shadow-hi); border-color:{v['muted']}66!important;
}}

/* inputs */
[data-baseweb="input"], [data-baseweb="select"]>div,
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
textarea {{
  border-radius:var(--r-sm)!important;
}}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {{
  background:var(--surface2); color:var(--text);
}}

/* metrics */
[data-testid="stMetric"] {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:16px; box-shadow:var(--shadow);
}}
[data-testid="stMetricValue"] {{ color:{v['teal']}; font-weight:800; }}
[data-testid="stMetricLabel"] {{ color:var(--muted); }}

/* tabs */
[data-baseweb="tab-list"] {{ gap:6px; border-bottom:1px solid var(--border); }}
[data-baseweb="tab"] {{
  background:transparent; border-radius:var(--r-sm) var(--r-sm) 0 0;
  font-weight:600; color:var(--muted); padding:8px 16px;
}}
[data-baseweb="tab"][aria-selected="true"] {{
  color:{v['teal']}; background:var(--surface);
  border-bottom:2px solid {v['teal']};
}}
[data-testid="stDataFrame"] {{ border-radius:var(--r-md); overflow:hidden; }}
[data-testid="stExpander"] {{
  border:1px solid var(--border); border-radius:var(--r-lg);
  background:var(--surface);
}}

/* premium building blocks - clean Vercel panel hero */
.rnr-hero {{
  position:relative; border-radius:var(--r-lg); padding:32px; margin-bottom:24px;
  background:var(--surface); border:1px solid var(--border);
  box-shadow:var(--shadow); overflow:hidden;
}}
.rnr-hero::after {{
  content:""; position:absolute; right:-80px; top:-120px; width:320px;
  height:320px; border-radius:var(--r-pill);
  background:radial-gradient({v['teal']}1f, transparent 70%);
}}
.rnr-hero .eyebrow {{ font-size:.72rem; letter-spacing:.16em;
  text-transform:uppercase; color:{v['teal']}; font-weight:700; }}
.rnr-hero h1 {{ color:var(--text); margin:.25rem 0 .3rem; font-size:2.1rem;
  font-weight:800; }}
.rnr-hero .sub {{ color:var(--muted); font-size:1rem; max-width:74ch; }}
.rnr-crumb {{ font-size:.8rem; color:var(--muted); margin-bottom:8px; }}
.rnr-crumb .sep {{ margin:0 7px; opacity:.6; }}
.rnr-crumb span:last-child {{ color:{v['teal']}; font-weight:600; }}
.rnr-statrow {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px;
  margin:-6px 0 22px; }}
.rnr-stat {{ background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:16px; box-shadow:var(--shadow);
  transition:.16s; }}
.rnr-stat:hover {{ border-color:{v['teal']}55; box-shadow:var(--shadow-hi); }}
.rnr-stat .v {{ font-size:1.7rem; font-weight:800; color:var(--text);
  line-height:1.1; }}
.rnr-stat .k {{ font-size:.74rem; color:var(--muted); font-weight:600;
  text-transform:uppercase; letter-spacing:.06em; margin-top:4px; }}
/* responsive: the fixed 4-column KPI grid and generous hero padding are
   sized for desktop - reflow instead of overflowing/crushing on narrower
   viewports (tested at 1440/1024/768/320 per the frontend skill's checklist) */
@media (max-width:1024px) {{
  .rnr-statrow {{ grid-template-columns:repeat(2,1fr); }}
}}
@media (max-width:480px) {{
  .rnr-hero {{ padding:20px; }}
  .rnr-hero h1 {{ font-size:1.6rem; }}
  .rnr-statrow {{ grid-template-columns:1fr; }}
}}
.rnr-empty {{ text-align:center; padding:56px 24px; border:1.5px dashed
  var(--border); border-radius:var(--r-lg); background:var(--surface2);
  margin-top:8px; }}
.rnr-empty .ic {{ font-size:3rem; }}
.rnr-empty .t {{ font-size:1.2rem; font-weight:800; margin-top:8px;
  color:var(--text); }}
.rnr-empty .s {{ color:var(--muted); margin-top:4px; }}
/* .rnr-section renders on a real <h2> (see ui.section()) so screen-reader
   users get an actual heading, not silent styled divs, when navigating a
   long config form by heading - the h1..h4 rule above already sets
   font-weight/letter-spacing generically, these declarations (higher
   specificity) are what actually take effect */
.rnr-section {{ display:flex; align-items:center; gap:10px; margin:2px 0 10px;
  font-weight:700; font-size:1.02rem; color:var(--text); }}
.rnr-section .ic {{ width:30px; height:30px; border-radius:var(--r-sm);
  display:inline-flex; align-items:center; justify-content:center;
  background:{v['teal']}14; color:{v['teal']}; font-size:1rem;
  border:1px solid {v['teal']}33; }}
.rnr-pill {{ display:inline-flex; align-items:center; gap:6px;
  padding:4px 12px; border-radius:var(--r-pill); font-weight:700;
  font-size:.8rem; white-space:nowrap; }}
.rnr-pill.pass {{ background:{v['teal']}1f; color:{v['teal']};
  border:1px solid {v['teal']}55; }}
.rnr-pill.fail {{ background:#e5393522; color:#e35335;
  border:1px solid #e3533566; }}
.rnr-pill.idle {{ background:var(--surface2); color:var(--muted);
  border:1px solid var(--border); }}
.rnr-dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
/* compact list rows (the projects dashboard, via st.container(key="proj_list"),
   which Streamlit stamps with the .st-key-proj_list class below) - collapse
   Streamlit's default block gap and give each row a slim divider + hover
   highlight instead of the tall default st.columns()/st.divider() rhythm */
/* .st-key-proj_list lands on the SAME element as its own stVerticalBlock
   (Streamlit stamps the key class directly onto the container, not a
   wrapper around it) - match both that element and any nested vertical
   block, or the outer row-to-row flex gap (16px by default) survives */
.st-key-proj_list[data-testid="stVerticalBlock"],
.st-key-proj_list [data-testid="stVerticalBlock"] {{ gap:0 !important; }}
.st-key-proj_list [data-testid="stHorizontalBlock"] {{
  padding:8px; margin:0 !important; border-radius:var(--r-sm);
  align-items:center; transition:background .12s ease;
}}
.st-key-proj_list [data-testid="stHorizontalBlock"]:hover {{
  background:var(--surface2);
}}
.st-key-proj_list hr {{ margin:0 !important; opacity:.6; }}
.rnr-row-title {{ font-weight:700; font-size:.92rem; line-height:1.3; }}
.rnr-row-meta {{ color:var(--muted); font-size:.74rem; line-height:1.3; }}
/* the 8-column row (name/ID/SO/rev/systems/configs/status/actions) has no
   room to breathe under ~900px - Streamlit's columns are server-rendered
   from fixed ratios, so there's no Python-side "stack on mobile"; drop the
   secondary columns (2nd-6th: Project ID, SO No, Rev, Systems, Configs)
   via CSS instead and let name/status/actions expand to fill the row
   (display:none fully removes them from the flex layout, so the survivors
   grow to fill the freed space - not just leave a gap) */
@media (max-width:900px) {{
  .st-key-proj_list [data-testid="stColumn"]:nth-of-type(2),
  .st-key-proj_list [data-testid="stColumn"]:nth-of-type(3),
  .st-key-proj_list [data-testid="stColumn"]:nth-of-type(4),
  .st-key-proj_list [data-testid="stColumn"]:nth-of-type(5),
  .st-key-proj_list [data-testid="stColumn"]:nth-of-type(6) {{
    display:none;
  }}
  /* Streamlit hides the SECOND of a nested column pair outright at narrow
     widths as its own built-in behavior (computed display:none, confirmed
     via devtools - not a wrapping/height issue) - deleting a project has
     no other entry point in this app, so silently losing the button here
     would strand the capability, not just make it "harder to tap". Force
     it back on and keep both buttons on one shrunk-to-fit line. */
  .st-key-proj_list [data-testid="stColumn"]:nth-of-type(8)
    [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; }}
  .st-key-proj_list [data-testid="stColumn"]:nth-of-type(8)
    [data-testid="stColumn"] {{
    display:block !important; min-width:0 !important;
  }}
  .st-key-proj_list [data-testid="stColumn"]:nth-of-type(8) button {{
    padding-left:.5rem; padding-right:.5rem;
  }}
}}
/* the page-header action row (title + "Create new project") also has no
   room at tablet/phone widths - stack it instead of letting the button
   clip off the right edge (same breakpoint as the list above, for one
   consistent "narrow" behavior across the dashboard) */
@media (max-width:900px) {{
  .st-key-dash_top [data-testid="stHorizontalBlock"] {{ flex-wrap:wrap; }}
  .st-key-dash_top [data-testid="stColumn"] {{
    min-width:100% !important; flex:1 1 100% !important;
  }}
}}
.rnr-tile {{ background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:16px; box-shadow:var(--shadow); }}
.rnr-tile .k {{ color:var(--muted); font-size:.78rem; font-weight:600;
  text-transform:uppercase; letter-spacing:.06em; }}
.rnr-tile .v {{ color:{v['teal']}; font-size:1.5rem; font-weight:800; }}
.rnr-chiprow {{ display:flex; gap:8px; flex-wrap:wrap; }}
.rnr-muted {{ color:var(--muted); }}
.rnr-topbar {{ display:flex; align-items:center; gap:10px; margin:-8px 0 18px;
  padding:8px 16px; border-radius:var(--r-md); font-size:.86rem; font-weight:600;
  background:linear-gradient(90deg,{v['teal']}14,{v['teal']}05);
  border:1px solid {v['teal']}33; color:var(--text); }}
.rnr-topbar .ic {{ font-size:1rem; }}
/* CAD-style command/log bar pinned to the bottom of the page */
.rnr-console {{ position:fixed; left:0; right:0; bottom:0; z-index:999990;
  background:var(--surface); border-top:2px solid {v['teal']};
  box-shadow:0 -4px 16px rgba(0,0,0,.10); transition:left .2s ease;
  font-family:'JetBrains Mono',ui-monospace,monospace; }}
/* keep the bar in the content area so an expanded sidebar can't cover it */
[data-testid="stApp"]:has([data-testid="stSidebar"][aria-expanded="true"])
  .rnr-console {{ left:21rem; }}
.rnr-console .hd {{ display:flex; align-items:center; gap:8px;
  padding:6px 16px; border-bottom:1px solid var(--border);
  font-size:.8rem; font-weight:700; color:var(--text); }}
.rnr-console .hd .dot {{ width:9px; height:9px; border-radius:50%;
  background:{v['teal']}; box-shadow:0 0 0 3px {v['teal']}33; }}
.rnr-console .hd .dot.err {{ background:#e35335; box-shadow:0 0 0 3px #e3533533; }}
.rnr-console .hd .lbl {{ color:var(--muted); font-weight:600;
  text-transform:uppercase; letter-spacing:.08em; font-size:.66rem; }}
.rnr-console .body {{ height:104px; overflow-y:auto; padding:6px 16px 8px;
  display:flex; flex-direction:column; gap:1px; }}
.rnr-console .ln {{ color:var(--muted); font-size:.74rem; line-height:1.55;
  white-space:pre-wrap; }}
.rnr-console .ln .t {{ color:{v['teal']}; }}
.rnr-console .ln.err {{ color:#e35335; }}
.rnr-console .ln.ok {{ color:{v['teal']}; font-weight:600; }}
.rnr-cmp {{ background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:8px 16px 16px; box-shadow:var(--shadow);
  height:100%; }}
.rnr-cmp-head {{ display:flex; align-items:center; justify-content:space-between;
  gap:8px; padding:12px 0 10px; border-bottom:1px solid var(--border);
  margin-bottom:6px; }}
.rnr-cmp-head .t {{ font-weight:800; font-size:1.05rem; color:var(--text);
  letter-spacing:-.01em; }}
.rnr-cmp-row {{ padding:8px 0; border-bottom:1px solid var(--border); }}
.rnr-cmp-row:last-child {{ border-bottom:none; }}
.rnr-cmp-row .k {{ font-size:.72rem; color:var(--muted); font-weight:600;
  text-transform:uppercase; letter-spacing:.05em; }}
.rnr-cmp-row .v {{ font-size:1.02rem; font-weight:700; color:var(--text);
  margin-top:1px; }}
.rnr-cmp-bar {{ margin-top:6px; height:6px; border-radius:var(--r-pill);
  background:var(--surface2); border:1px solid var(--border);
  overflow:hidden; }}
.rnr-cmp-bar span {{ display:block; height:100%; border-radius:var(--r-pill); }}
#MainMenu, footer, [data-testid="stToolbar"] {{ visibility:hidden; }}
</style>""", unsafe_allow_html=True)


def hero(title: str, subtitle: str = "", eyebrow: str = "",
         crumbs=None) -> None:
    cb = ""
    if crumbs:
        parts = '<span class="sep">›</span>'.join(
            f'<span>{_html.escape(c)}</span>' for c in crumbs)
        cb = f'<div class="rnr-crumb">{parts}</div>'
    eb = (f'<div class="eyebrow">{_html.escape(eyebrow)}</div>'
          if eyebrow else "")
    sub = f'<div class="sub">{_html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(f'<div class="rnr-hero">{cb}{eb}<h1>{_html.escape(title)}</h1>'
                f'{sub}</div>', unsafe_allow_html=True)


def stat_strip(stats) -> None:
    """A row of compact KPI tiles: stats = [(label, value), ...]."""
    cells = "".join(
        f'<div class="rnr-stat"><div class="v">{_html.escape(str(v))}</div>'
        f'<div class="k">{_html.escape(k)}</div></div>' for k, v in stats)
    st.markdown(f'<div class="rnr-statrow">{cells}</div>',
                unsafe_allow_html=True)


def empty_state(icon: str, title: str, text: str = "") -> None:
    # role="status" so a screen reader announces it when it appears
    # dynamically (e.g. a search that now matches nothing), not just on
    # first paint
    st.markdown(
        f'<div class="rnr-empty" role="status"><div class="ic" '
        f'aria-hidden="true">{icon}</div>'
        f'<div class="t">{_html.escape(title)}</div>'
        f'<div class="s">{_html.escape(text)}</div></div>',
        unsafe_allow_html=True)


def pill(verdict: str) -> str:
    v = (verdict or "not run").upper()
    cls = "pass" if v == "PASS" else "fail" if v == "FAIL" else "idle"
    # the dot is decorative (colour), the text label already carries the
    # status - hidden from screen readers so it isn't announced as noise
    return (f'<span class="rnr-pill {cls}"><span class="rnr-dot" '
            f'aria-hidden="true" style="background:currentColor"></span>'
            f'{_html.escape(v)}</span>')


def role_badge(is_admin: bool) -> str:
    """Small ADMIN/USER badge, reusing the pill palette (admin = teal)."""
    cls = "pass" if is_admin else "idle"
    label = "ADMIN" if is_admin else "USER"
    return f'<span class="rnr-pill {cls}">{label}</span>'


def sidebar_brand(name: str, tagline: str) -> None:
    st.markdown(
        f'<div class="rnr-sb-brand"><div>'
        f'<div class="name">{_html.escape(name)}</div>'
        f'<div class="tag">{_html.escape(tagline)}</div></div></div>',
        unsafe_allow_html=True)


def sidebar_chip(label: str, value: str) -> None:
    """A compact key/value chip for sidebar context (e.g. current project) -
    lighter-weight than st.info, which reads as a full alert box."""
    st.markdown(
        f'<div class="rnr-sbchip"><div class="k">{_html.escape(label)}</div>'
        f'<div class="v">{_html.escape(value)}</div></div>',
        unsafe_allow_html=True)


def sidebar_profile(name: str, username: str, is_admin: bool) -> None:
    initial = (name or username or "?").strip()[:1].upper()
    st.markdown(
        f'<div class="rnr-profile"><div class="av">{_html.escape(initial)}'
        f'</div><div class="meta"><div class="nm">'
        f'{_html.escape(name or username)}</div><div>'
        f'{role_badge(is_admin)}<span class="un">@{_html.escape(username)}'
        f'</span></div></div></div>', unsafe_allow_html=True)


def sidebar_footer(lines) -> None:
    """Condensed footer block - one compact paragraph instead of several
    separate st.caption() calls, each with their own margin."""
    st.markdown(f'<div class="rnr-sbfooter">{"<br>".join(lines)}</div>',
                unsafe_allow_html=True)


def tile(label: str, value: str) -> str:
    return (f'<div class="rnr-tile"><div class="k">{_html.escape(label)}</div>'
            f'<div class="v">{_html.escape(str(value))}</div></div>')


def section(icon: str, title: str) -> None:
    """An icon + title header for a form section card, rendered as a real
    <h2> - screen-reader users can jump between sections (masters, beam
    levels, bracing, ...) via heading navigation, not just sighted users
    scanning styled divs. hero() renders the page's one <h1>, so this is the
    correct next level (st.subheader()'s native <h3> nests under it)."""
    st.markdown(f'<h2 class="rnr-section"><span class="ic" aria-hidden="true">'
                f'{icon}</span>{_html.escape(title)}</h2>',
                unsafe_allow_html=True)


# --------------------------------------------------------------- command log
_CONSOLE_PH = None       # placeholder for the live bottom console


def log(msg: str, level: str = "info") -> None:
    """Append a line to the persistent command log (session-scoped) and, if the
    bottom command bar is already on the page, refresh it live."""
    buf = st.session_state.setdefault("_log", [])
    buf.append((_time.strftime("%H:%M:%S"), level, str(msg)))
    if len(buf) > 500:
        del buf[:-500]
    _render_console()


def console() -> None:
    """Create / render the CAD-style command bar pinned to the page bottom.
    Call once per page (early), so runs can update it live afterwards."""
    global _CONSOLE_PH
    _CONSOLE_PH = st.empty()
    _render_console()


def _render_console() -> None:
    if _CONSOLE_PH is None:
        return
    buf = st.session_state.get("_log", [])
    latest = buf[-1] if buf else ("", "info", "Ready")
    rows = []
    for ts, lvl, msg in reversed(buf[-200:]):       # newest first = always seen
        cls = "err" if lvl == "error" else "ok" if lvl == "ok" else ""
        rows.append(f'<div class="ln {cls}"><span class="t">{ts}</span>  '
                    f'{_html.escape(msg)}</div>')
    body = "".join(rows) or '<div class="ln">Ready.</div>'
    dot = "err" if latest[1] == "error" else ""
    _CONSOLE_PH.markdown(
        f'<div class="rnr-console"><div class="hd">'
        f'<span class="dot {dot}"></span><span class="lbl">command log</span>'
        f'<span>{_html.escape(latest[2])}</span></div>'
        f'<div class="body">{body}</div></div>', unsafe_allow_html=True)


def run_with_status(run_fn, label="Running analysis"):
    """Execute run_fn(progress=cb) showing a staged status box, a progress bar,
    and the elapsed time; returns run_fn's result.  Each stage line carries the
    running elapsed time, so the most recent (bottom) line always shows it; the
    stages cover both the second-order analysis and the seismic run, and are
    streamed live to the bottom command log."""
    box = st.status(f"⚙️  {label}…", expanded=True)
    bar = box.progress(0.0)
    start = _time.time()
    log(f"▶ {label}")
    _render_console()

    def cb(stage, frac):
        bar.progress(min(max(frac, 0.0), 1.0))
        el = _time.time() - start
        box.write(f"• {stage}  ·  ⏱ {el:.0f}s")
        log(f"{stage}  ({el:.0f}s)")
        _render_console()
    try:
        result = run_fn(progress=cb)
    except Exception as exc:                      # surface failures, don't hang
        box.update(label=f"❌  Run failed after {_time.time()-start:.0f}s",
                   state="error", expanded=True)
        box.write(f"Error: {exc}")
        log(f"FAILED: {exc}", "error")
        _render_console()
        # echo to the command prompt (terminal running Streamlit)
        print(f"ANALYSIS STOPPED: {exc}", file=_sys.stderr, flush=True)
        raise
    total = _time.time() - start
    bar.progress(1.0)
    box.update(label=f"✅  Analysis complete in {total:.0f}s",
               state="complete", expanded=False)
    log(f"✓ {label} complete in {total:.0f}s", "ok")
    _render_console()
    return result


CANCELLED = object()      # sentinel returned by run_cancellable_poll on cancel


def run_cancellable_poll(run_fn, label="Running analysis", key="run"):
    """Run run_fn(progress=cb, should_cancel=fn) in a background thread so the
    user can cancel it with a Stop button.  Drives itself by short reruns while
    the worker is alive (it calls st.rerun() and does NOT return in that case).

    WARNING: NOT suitable for OpenSees runs - the solver must stay on the main
    thread, and the rerun polling loop re-executes the whole page every cycle,
    starving the worker (the app appears stuck at the first stage).  Use
    run_with_status for analyses; keep this only for light, thread-safe tasks.

    Returns one of:
      ("running", None)   - never actually returned (a rerun is triggered first)
      ("done", result)    - worker finished; result is run_fn's return value
      ("cancelled", None) - the user pressed Stop
      ("error", exc)      - worker raised exc (e.g. UnstableModelError)
    """
    import threading
    from .analysis import RunCancelled
    hk = f"_crun_{key}"
    h = st.session_state.get(hk)
    if h is None:
        h = {"stages": [], "frac": 0.0, "done": False, "result": None,
             "error": None, "cancelled": False, "start": _time.time(),
             "event": threading.Event()}

        def cb(stage, frac):
            h["stages"].append((stage, _time.time() - h["start"]))
            h["frac"] = min(max(frac, 0.0), 1.0)

        def worker():
            try:
                h["result"] = run_fn(progress=cb,
                                     should_cancel=h["event"].is_set)
            except RunCancelled:
                h["cancelled"] = True
            except Exception as exc:               # captured, surfaced on the
                h["error"] = exc                   # main thread when done
            finally:
                h["done"] = True

        t = threading.Thread(target=worker, daemon=True)
        st.session_state[hk] = h
        log(f"▶ {label}")
        _render_console()
        t.start()

    box = st.status(f"⚙️  {label}…",
                    expanded=True, state="running" if not h["done"] else "complete")
    box.progress(h["frac"])
    last = ""
    for stage, el in h["stages"][-14:]:
        box.write(f"• {stage}  ·  ⏱ {el:.0f}s")
        last = stage
    if last:
        log(last, "ok")
        _render_console()

    if not h["done"]:
        if st.button("⛔ Stop analysis", key=f"_stop_{key}", type="secondary"):
            h["event"].set()
            box.write("⛔ Stop requested — cancelling after the current run…")
        _time.sleep(0.4)
        st.rerun()                                 # poll again (exits here)

    # finished -> clear holder so the next run starts fresh
    st.session_state[hk] = None
    total = _time.time() - h["start"]
    if h["cancelled"]:
        box.update(label=f"⛔ Analysis cancelled after {total:.0f}s",
                   state="error", expanded=False)
        log("⛔ Analysis cancelled by user", "warn")
        _render_console()
        return ("cancelled", None)
    if h["error"] is not None:
        box.update(label=f"❌ Run failed after {total:.0f}s",
                   state="error", expanded=True)
        box.write(f"Error: {h['error']}")
        log(f"FAILED: {h['error']}", "error")
        _render_console()
        return ("error", h["error"])
    box.update(label=f"✅  Analysis complete in {total:.0f}s",
               state="complete", expanded=False)
    log(f"✓ {label} complete in {total:.0f}s", "ok")
    _render_console()
    return ("done", h["result"])


def run_in_background(config_dir: str, label: str = "Running analysis",
                      key: str = "run"):
    """Poll a rack15512.background_run-started subprocess via its on-disk
    status file, rendering the same staged status box / progress bar / Stop
    button as run_cancellable_poll.  Unlike run_cancellable_poll (a thread,
    tied to this session's state), the run itself is a separate OS process
    started by rack15512.background_run.start_run() - a Streamlit rerun
    (from any click, anywhere) never touches it, and polling works from any
    browser session or after a full page refresh since the status lives on
    disk, not in session_state.  Drives itself by short reruns while the run
    is not done (it calls st.rerun() and does NOT return in that case).

    Returns one of:
      ("done", summary)   - run finished; summary is the run's result dict
      ("cancelled", None) - the user pressed Stop (or another session did)
      ("error", status)   - run raised; status carries "error"/"error_type"
    """
    from .background_run import poll_status, request_cancel
    status = poll_status(config_dir) or {
        "done": False, "stage": "Starting…", "frac": 0.0, "elapsed": 0.0}

    box = st.status(f"⚙️  {label}…", expanded=True,
                    state="running" if not status["done"] else "complete")
    box.progress(min(max(status.get("frac", 0.0), 0.0), 1.0))
    stage = status.get("stage") or ""
    el = status.get("elapsed", 0.0)
    if stage:
        box.write(f"• {stage}  ·  ⏱ {el:.0f}s")
        log(f"{stage}  ({el:.0f}s)")
        _render_console()

    if not status["done"]:
        if st.button("⛔ Stop analysis", key=f"_stop_{key}", type="secondary"):
            if request_cancel(config_dir):
                box.write("⛔ Stop requested — cancelling after the current "
                          "step…")
        _time.sleep(0.6)
        st.rerun()                                 # poll again (exits here)

    total = status.get("elapsed", 0.0)
    if status.get("cancelled"):
        box.update(label=f"⛔ Analysis cancelled after {total:.0f}s",
                   state="error", expanded=False)
        log("⛔ Analysis cancelled by user", "warn")
        _render_console()
        return ("cancelled", None)
    if status.get("error"):
        box.update(label=f"❌ Run failed after {total:.0f}s",
                   state="error", expanded=True)
        box.write(f"Error: {status['error']}")
        log(f"FAILED: {status['error']}", "error")
        _render_console()
        return ("error", status)
    box.update(label=f"✅  Analysis complete in {total:.0f}s",
               state="complete", expanded=False)
    log(f"✓ {label} complete in {total:.0f}s", "ok")
    _render_console()
    return ("done", status.get("summary"))


def theme_toggle() -> None:
    cur = st.toggle("🌙 Dark mode", key="dark_mode")
    if cur != load_dark_pref():
        _save_dark_pref(cur)


def render_login(user_store) -> None:
    """Centered sign-in gate.  Call once apply_theme() has run; the caller
    is responsible for st.stop()-ing right after this when no one is signed
    in yet (see app_streamlit.py) - nothing else on the page should render
    until st.session_state["user"] is set here on a successful login."""
    st.markdown('<div style="height:9vh"></div>', unsafe_allow_html=True)
    col = st.columns([1, 1.1, 1])[1]
    with col:
        with st.container(border=True):
            if _os.path.exists(B.LOGO_PATH):
                lc = st.columns([1, 2, 1])[1]
                lc.image(B.LOGO_PATH, width="stretch")
            st.markdown(
                f"<h2 style='text-align:center;margin:6px 0 2px'>"
                f"{_html.escape(B.PRODUCT)}</h2>"
                f"<p class='rnr-muted' style='text-align:center;"
                f"margin-bottom:18px'>Sign in to continue</p>",
                unsafe_allow_html=True)
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button(
                    "Sign in", type="primary", width="stretch")
            if submitted:
                user = user_store.verify_login(username, password)
                if user is None:
                    st.error("Incorrect username or password.")
                else:
                    st.session_state["user"] = {
                        "username": user.username, "name": user.name,
                        "role": user.role}
                    st.rerun()
        st.markdown(
            f"<div class='rnr-muted' style='text-align:center;"
            f"margin-top:12px;font-size:.82rem'>© {B.COMPANY} · "
            f"internal tool — access is restricted to authorised users</div>",
            unsafe_allow_html=True)


def toast_verdict(verdict: str) -> None:
    """Pop a short toast announcing the analysis outcome."""
    v = (verdict or "").upper()
    if v == "PASS":
        st.toast("Analysis complete — design **PASSES** EN 15512.", icon="✅")
    elif v == "FAIL":
        st.toast("Analysis complete — design **FAILS** one or more checks.",
                 icon="⚠️")
    else:
        st.toast("Analysis complete.", icon="✅")


def topbar(message: str, kind: str = "info") -> None:
    """A slim announcement strip pinned across the top of the page."""
    palette = {
        "info": ("teal", "💡"),
        "tip": ("teal", "✨"),
        "warn": ("grey", "⚠️"),
    }
    _, icon = palette.get(kind, palette["info"])
    st.markdown(
        f'<div class="rnr-topbar"><span class="ic">{icon}</span>'
        f'<span>{_html.escape(message)}</span></div>',
        unsafe_allow_html=True)


def compare_card(title: str, rows, verdict: str = "") -> str:
    """Render one configuration column for the side-by-side comparison.

    rows = [(label, value, ratio_or_None)]; ratio in [0,1] draws a util bar.
    """
    head = (f'<div class="rnr-cmp-head"><div class="t">{_html.escape(title)}'
            f'</div>{pill(verdict) if verdict else ""}</div>')
    body = []
    for label, value, ratio in rows:
        bar = ""
        if ratio is not None:
            pct = max(0.0, min(float(ratio), 1.0)) * 100
            over = float(ratio) > 1.0
            col = "#e35335" if over else "var(--teal)"
            bar = (f'<div class="rnr-cmp-bar"><span style="width:{pct:.0f}%;'
                   f'background:{col}"></span></div>')
        body.append(
            f'<div class="rnr-cmp-row"><div class="k">{_html.escape(label)}'
            f'</div><div class="v">{_html.escape(str(value))}</div>{bar}</div>')
    return f'<div class="rnr-cmp">{head}{"".join(body)}</div>'
