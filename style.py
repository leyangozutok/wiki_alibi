"""Shared look of Wiki Alibi (all pages): a warm 'case file' atmosphere, still simple and readable."""
import html as H

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;700&family=Courier+Prime:wght@400;700&display=swap');
:root{--ink:#2B2623;--rust:#B4552D;--paper:#FFFDF8;--line:#E2D8C3;--muted:#7a7066;--green:#3F7D58;--gold:#C79A3B}
.block-container{padding-top:4.2rem;padding-bottom:3rem;max-width:1500px}
header[data-testid="stHeader"]{background:transparent}
footer,#MainMenu,[data-testid="stSidebar"],[data-testid="collapsedControl"]{display:none!important}
[data-testid="stForm"]{border:none;padding:0;background:transparent}
h1,h2,h3{font-family:'Playfair Display',Georgia,serif!important;color:var(--ink)}
.wa-brand{font-family:'Playfair Display',Georgia,serif;font-size:1.9rem;font-weight:700;line-height:1.1;color:var(--ink)}
.wa-brand small{font-family:'Courier Prime',monospace;font-size:.7rem;letter-spacing:.2em;color:var(--rust);
  display:block;font-weight:400;margin-top:.25rem}
.wa-label{font-family:'Courier Prime',monospace;font-size:.78rem;letter-spacing:.2em;text-transform:uppercase;
  color:var(--rust);border-bottom:1px solid var(--line);padding-bottom:.4rem;margin:1.7rem 0 .8rem}
.wa-muted{font-size:.88rem;color:var(--muted);line-height:1.55}
.wa-hero{font-family:'Playfair Display',Georgia,serif;font-size:2.7rem;line-height:1.15;font-weight:700;margin:.4rem 0 .8rem}
.wa-hero em{color:var(--rust);font-style:italic}
.wa-lead{font-size:1.08rem;line-height:1.7;max-width:36rem;margin-bottom:1.2rem}
.wa-badge{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:.55rem .9rem}
.wa-badge b{font-family:'Playfair Display',serif;font-size:1.05rem}
.wa-badge .r{font-family:'Courier Prime',monospace;font-size:.72rem;letter-spacing:.12em;color:var(--rust);text-transform:uppercase}
.wa-progress{height:.38rem;background:#E9E0CE;border-radius:9px;margin-top:.4rem;overflow:hidden}
.wa-progress>div{height:100%;background:var(--rust);border-radius:9px}
.wa-casehead{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem}
.wa-casenum{font-family:'Courier Prime',monospace;font-size:.78rem;letter-spacing:.18em;color:var(--muted);text-transform:uppercase}
.wa-casename{font-family:'Playfair Display',Georgia,serif;font-size:2rem;font-weight:700;line-height:1.15}
.wa-stamp{display:inline-block;border:3px double var(--rust);color:var(--rust);padding:.15rem .7rem;
  transform:rotate(-5deg);font-family:'Courier Prime',monospace;font-weight:700;letter-spacing:.18em;
  text-transform:uppercase;font-size:.85rem;opacity:.85}
.wa-stamp.ok{border-color:var(--green);color:var(--green)}
.wa-brief{font-size:1.03rem;line-height:1.75;margin:.9rem 0 .6rem;padding:.2rem 0 .2rem 1rem;border-left:3px solid var(--gold)}
.wa-steps{display:flex;flex-wrap:wrap;gap:.4rem .5rem;margin:.4rem 0 .2rem}
.wa-steps span{font-size:.78rem;background:#EFE7D6;border-radius:99px;padding:.2rem .7rem;color:#5c5249}
.wa-card{display:flex;gap:.9rem;align-items:flex-start;background:var(--paper);border:1px solid var(--line);
  border-left:4px solid var(--rust);border-radius:6px;padding:.75rem 1rem;margin:.5rem 0;line-height:1.55;
  box-shadow:0 1px 2px rgba(60,40,20,.06)}
.wa-num{flex:none;width:1.7rem;height:1.7rem;border-radius:50%;background:var(--rust);color:#fff;
  font-family:'Courier Prime',monospace;font-weight:700;display:flex;align-items:center;justify-content:center;font-size:.9rem}
.wa-witness{display:flex;gap:.8rem;align-items:center;margin-bottom:.6rem}
.wa-avatar{flex:none;width:2.6rem;height:2.6rem;border-radius:50%;background:#E9DDC4;border:2px solid var(--gold);
  display:flex;align-items:center;justify-content:center;font-family:'Playfair Display',serif;font-weight:700}
.wa-msg{margin:.45rem 0;display:flex;flex-direction:column}
.wa-msg.you{align-items:flex-end}
.wa-who{font-family:'Courier Prime',monospace;font-size:.68rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:.15rem}
.wa-bubble{max-width:88%;padding:.55rem .85rem;border-radius:12px;line-height:1.5;background:var(--paper);border:1px solid var(--line)}
.wa-msg.you .wa-bubble{background:#F3DFD3;border-color:#E6C7B4}
.wa-notebook{font-family:'Courier Prime',monospace;font-size:.8rem;color:var(--muted);margin:.2rem 0 .4rem}
.wa-verdict{font-family:'Playfair Display',serif;font-size:1.7rem;font-weight:700;margin:.5rem 0}
.wa-note{background:#FBF3DD;border:1px solid #EBD79B;border-radius:8px;padding:.8rem 1rem;margin:.8rem 0;line-height:1.6}
.wa-note b{font-family:'Courier Prime',monospace;font-size:.72rem;letter-spacing:.15em;text-transform:uppercase;color:#8a6a14;display:block;margin-bottom:.25rem}
.wa-up{background:var(--green);color:#fff;border-radius:8px;padding:.6rem 1rem;margin:.6rem 0;font-weight:600}
.wa-stat{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:.8rem 1rem}
.wa-stat .n{font-family:'Playfair Display',serif;font-size:2rem;font-weight:700;line-height:1.1}
.wa-stat .t{font-size:.82rem;color:var(--muted)}
.wa-bar{display:flex;align-items:center;gap:.9rem;margin:.32rem 0}
.wa-bl{width:8rem;flex:none;font-size:.88rem}
.wa-track{flex:1;height:.6rem;background:#E9E0CE;border-radius:9px;overflow:hidden}
.wa-fill{height:100%;border-radius:9px}
.wa-fill.me{background:var(--rust)}.wa-fill.all{background:#5b6f82}.wa-fill.bot{background:#9aa3ad}.wa-fill.rand{background:#d9cfb9}
.wa-bv{width:7.2rem;flex:none;text-align:right;font-size:.8rem;color:var(--muted)}
.wa-explain{background:var(--paper);border:1px dashed #cdbf9f;border-radius:10px;padding:.9rem 1.1rem;line-height:1.65}
.wa-explain ol{margin:.3rem 0 .3rem 1.1rem;padding:0}
.wa-table{width:100%;border-collapse:collapse;font-size:.88rem}
.wa-table th{font-family:'Courier Prime',monospace;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;font-weight:400;
  color:var(--muted);text-align:left;padding:.4rem .5rem;border-bottom:1px solid var(--line)}
.wa-table td{padding:.5rem;border-bottom:1px solid #EFE7D6}
.wa-tag{display:inline-block;border-radius:99px;padding:.05rem .6rem;font-size:.78rem;font-weight:600}
.wa-tag.ok{background:#DCEBDD;color:#2f6b45}.wa-tag.no{background:#F3D9D0;color:#9a3f20}
</style>
"""


def esc(x) -> str:
    return H.escape(str(x))


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def label(text: str) -> None:
    st.markdown(f'<div class="wa-label">{esc(text)}</div>', unsafe_allow_html=True)


def bar(label_text: str, pct: float, text: str, cls: str = "me") -> str:
    pct = max(0.0, min(100.0, pct))
    return (f'<div class="wa-bar"><span class="wa-bl">{esc(label_text)}</span>'
            f'<div class="wa-track"><div class="wa-fill {cls}" style="width:{pct:.0f}%"></div></div>'
            f'<span class="wa-bv">{esc(text)}</span></div>')


def progress(frac: float) -> str:
    return f'<div class="wa-progress"><div style="width:{max(0.0, min(1.0, frac)) * 100:.0f}%"></div></div>'
