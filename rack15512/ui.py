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
  border-radius:8px;
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
  border-radius:12px; box-shadow:var(--shadow); padding:6px;
  transition:.16s ease;
}}
[data-testid="stVerticalBlockBorderWrapper"]:hover {{
  box-shadow:var(--shadow-hi); border-color:{v['muted']}66!important;
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

/* premium building blocks - clean Vercel panel hero */
.rnr-hero {{
  position:relative; border-radius:14px; padding:30px 32px; margin-bottom:24px;
  background:var(--surface); border:1px solid var(--border);
  box-shadow:var(--shadow); overflow:hidden;
}}
.rnr-hero::after {{
  content:""; position:absolute; right:-80px; top:-120px; width:320px;
  height:320px; border-radius:50%;
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
.rnr-statrow {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px;
  margin:-6px 0 22px; }}
.rnr-stat {{ background:var(--surface); border:1px solid var(--border);
  border-radius:14px; padding:16px 18px; box-shadow:var(--shadow);
  transition:.16s; }}
.rnr-stat:hover {{ border-color:{v['teal']}55; box-shadow:var(--shadow-hi); }}
.rnr-stat .v {{ font-size:1.7rem; font-weight:800; color:var(--text);
  line-height:1.1; }}
.rnr-stat .k {{ font-size:.74rem; color:var(--muted); font-weight:600;
  text-transform:uppercase; letter-spacing:.06em; margin-top:4px; }}
.rnr-empty {{ text-align:center; padding:56px 24px; border:1.5px dashed
  var(--border); border-radius:18px; background:var(--surface2);
  margin-top:8px; }}
.rnr-empty .ic {{ font-size:3rem; }}
.rnr-empty .t {{ font-size:1.2rem; font-weight:800; margin-top:8px;
  color:var(--text); }}
.rnr-empty .s {{ color:var(--muted); margin-top:4px; }}
.rnr-section {{ display:flex; align-items:center; gap:10px; margin:2px 0 10px;
  font-weight:700; font-size:1.02rem; color:var(--text); }}
.rnr-section .ic {{ width:30px; height:30px; border-radius:9px;
  display:inline-flex; align-items:center; justify-content:center;
  background:{v['teal']}14; color:{v['teal']}; font-size:1rem;
  border:1px solid {v['teal']}33; }}
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
.rnr-topbar {{ display:flex; align-items:center; gap:10px; margin:-8px 0 18px;
  padding:9px 16px; border-radius:12px; font-size:.86rem; font-weight:600;
  background:linear-gradient(90deg,{v['teal']}14,{v['teal']}05);
  border:1px solid {v['teal']}33; color:var(--text); }}
.rnr-topbar .ic {{ font-size:1rem; }}
.rnr-cmp {{ background:var(--surface); border:1px solid var(--border);
  border-radius:16px; padding:6px 16px 14px; box-shadow:var(--shadow);
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
.rnr-cmp-bar {{ margin-top:6px; height:6px; border-radius:999px;
  background:var(--surface2); border:1px solid var(--border);
  overflow:hidden; }}
.rnr-cmp-bar span {{ display:block; height:100%; border-radius:999px; }}
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
    st.markdown(
        f'<div class="rnr-empty"><div class="ic">{icon}</div>'
        f'<div class="t">{_html.escape(title)}</div>'
        f'<div class="s">{_html.escape(text)}</div></div>',
        unsafe_allow_html=True)


def pill(verdict: str) -> str:
    v = (verdict or "not run").upper()
    cls = "pass" if v == "PASS" else "fail" if v == "FAIL" else "idle"
    return (f'<span class="rnr-pill {cls}"><span class="rnr-dot" '
            f'style="background:currentColor"></span>{_html.escape(v)}</span>')


def tile(label: str, value: str) -> str:
    return (f'<div class="rnr-tile"><div class="k">{_html.escape(label)}</div>'
            f'<div class="v">{_html.escape(str(value))}</div></div>')


def section(icon: str, title: str) -> None:
    """An icon + title header for a form section card."""
    st.markdown(f'<div class="rnr-section"><span class="ic">{icon}</span>'
                f'{_html.escape(title)}</div>', unsafe_allow_html=True)


def run_with_status(run_fn, label="Running analysis"):
    """Execute run_fn(progress=cb) showing a staged status box, a progress bar,
    and the elapsed time; returns run_fn's result.  Each stage line carries the
    running elapsed time, so the most recent (bottom) line always shows it; the
    stages cover both the second-order analysis and the seismic run."""
    box = st.status(f"⚙️  {label}…", expanded=True)
    bar = box.progress(0.0)
    start = _time.time()

    def cb(stage, frac):
        bar.progress(min(max(frac, 0.0), 1.0))
        box.write(f"• {stage}  ·  ⏱ {_time.time() - start:.0f}s")
    try:
        result = run_fn(progress=cb)
    except Exception as exc:                      # surface failures, don't hang
        box.update(label=f"❌  Run failed after {_time.time()-start:.0f}s",
                   state="error", expanded=True)
        box.write(f"Error: {exc}")
        raise
    total = _time.time() - start
    bar.progress(1.0)
    box.update(label=f"✅  Analysis complete in {total:.0f}s",
               state="complete", expanded=False)
    return result


def theme_toggle() -> None:
    cur = st.toggle("🌙 Dark mode", key="dark_mode")
    if cur != load_dark_pref():
        _save_dark_pref(cur)


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
