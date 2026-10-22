# -*- coding: utf-8 -*-
"""Écran « Glassy OTP » : carte vitrée sombre à reflets dorés, saisie du code en cases, animation « Verifying… » (chiffres qui tournent
puis se rassemblent) et « Verified Successfully » (coche verte). Pur HTML / CSS : aucun composant externe."""

from __future__ import annotations

import html
import time

import streamlit as st

CODE_LEN = 6
GOLD, GOLD_2, GREEN = "#E0B13A", "#F5D27A", "#22C55E"

CSS = f"""
<style>
div.st-key-otp_card {{
  position:relative; overflow:hidden; border-radius:26px; padding:1.6rem 1.6rem 1.3rem;
  background:
    linear-gradient(115deg, transparent 18%, rgba(224,177,58,.10) 30%, transparent 42%),
    linear-gradient(65deg, transparent 52%, rgba(224,177,58,.16) 63%, transparent 72%),
    radial-gradient(120% 90% at 0% 0%, rgba(160,98,20,.38), transparent 55%),
    radial-gradient(110% 90% at 100% 100%, rgba(224,177,58,.20), transparent 55%),
    linear-gradient(160deg, #15110c 0%, #0b0a0a 60%, #14100a 100%);
  border:1px solid rgba(245,210,122,.28);
  box-shadow: 0 30px 70px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.10), inset 0 0 60px rgba(224,177,58,.05);
}}
div.st-key-otp_card::before {{ content:""; position:absolute; inset:0; pointer-events:none; border-radius:26px;
  background: linear-gradient(120deg, rgba(255,255,255,.07), transparent 25%, transparent 75%, rgba(255,255,255,.04)); }}
div.st-key-otp_card, div.st-key-otp_card p, div.st-key-otp_card label {{ color:#F3EBDD !important; }}
.otp-head {{ text-align:center; margin-bottom:.9rem; }}
.otp-key {{ width:46px; height:46px; margin:0 auto .7rem; border-radius:14px; display:grid; place-items:center;
  background:rgba(224,177,58,.10); border:1px solid rgba(224,177,58,.45); color:{GOLD_2}; box-shadow:0 0 22px rgba(224,177,58,.18); }}
.otp-head h3 {{ margin:0; font-size:1.35rem; font-weight:700; color:#fff; }}
.otp-head h3 b {{ color:{GOLD}; }}
.otp-head p {{ margin:.35rem 0 0; font-size:.84rem; color:rgba(243,235,221,.65) !important; }}
/* le champ du code : 6 cases dessinées derrière un seul champ */
div.st-key-otp_card [data-testid="stTextInput"] {{ max-width:330px; margin:.4rem auto .2rem; }}
div.st-key-otp_card [data-testid="stTextInput"] > div,
div.st-key-otp_card [data-testid="stTextInput"] [data-baseweb="input"],
div.st-key-otp_card [data-testid="stTextInput"] [data-baseweb="base-input"] {{ background:transparent !important; border:none !important; box-shadow:none !important; }}
div.st-key-otp_card [data-testid="stTextInput"] input {{
  font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace; font-size:1.5rem; font-weight:700; color:#fff !important;
  text-align:left; letter-spacing:0; padding:0 0 0 0; height:52px; width:{CODE_LEN * 52}px; max-width:100%; margin:0 auto;
  caret-color:{GOLD_2}; background-color:transparent !important;
  background-image: repeating-linear-gradient(90deg, rgba(255,255,255,.06) 0 44px, transparent 44px 52px);
  background-size:{CODE_LEN * 52 - 8}px 100%; background-repeat:no-repeat;
  border:none !important; border-radius:12px; word-spacing:0;
  letter-spacing:calc(52px - 1ch); text-indent:calc(22px - 0.5ch);
  -webkit-mask: none;
}}
div.st-key-otp_card [data-testid="stTextInput"] input:focus {{ box-shadow:0 0 0 2px rgba(224,177,58,.55), 0 0 24px rgba(224,177,58,.25) !important; }}
div.st-key-otp_card [data-testid="stTextInput"] [data-testid="stWidgetLabel"] {{ display:none; }}
.otp-cells {{ display:flex; justify-content:center; gap:8px; margin:.2rem 0 .5rem; }}
.otp-cells i {{ width:44px; height:52px; border-radius:12px; border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.05);
  display:grid; place-items:center; font-style:normal; font-weight:700; font-size:1.4rem; color:#fff; font-family:ui-monospace,Menlo,Consolas,monospace; }}
.otp-cells i.on {{ border-color:rgba(224,177,58,.7); box-shadow:0 0 14px rgba(224,177,58,.25); }}
.otp-resend {{ text-align:center; font-size:.8rem; color:rgba(243,235,221,.6); margin:.4rem 0 .6rem; }}
.otp-resend b {{ color:{GOLD_2}; }}
div.st-key-otp_card [data-testid^="stBaseButton-primary"], div.st-key-otp_card button[kind^="primary"] {{
  background:linear-gradient(180deg, {GOLD_2}, {GOLD}) !important; color:#2a1d00 !important; border:none !important; font-weight:700 !important;
  border-radius:12px !important; box-shadow:0 8px 22px rgba(224,177,58,.28);
}}
div.st-key-otp_card [data-testid^="stBaseButton-primary"] *, div.st-key-otp_card button[kind^="primary"] * {{ color:#2a1d00 !important; opacity:1 !important; }}
div.st-key-otp_card [data-testid^="stBaseButton-secondary"], div.st-key-otp_card button[kind="secondary"] {{ background:rgba(255,255,255,.06) !important; color:#F3EBDD !important; border:1px solid rgba(255,255,255,.16) !important; border-radius:12px !important; }}
div.st-key-otp_card [data-testid="stAlert"] {{ border-radius:12px; }}
/* animations */
@keyframes otp-scatter {{ 0% {{ transform:translate(0,0) rotate(0); opacity:1 }} 45% {{ transform:translate(var(--dx),var(--dy)) rotate(var(--rot)); opacity:1 }}
  75% {{ transform:translate(0,0) rotate(0) scale(.5); opacity:.8 }} 100% {{ transform:scale(0); opacity:0 }} }}
@keyframes otp-pop {{ 0% {{ transform:scale(0); opacity:0 }} 70% {{ transform:scale(1.15); opacity:1 }} 100% {{ transform:scale(1); opacity:1 }} }}
@keyframes otp-draw {{ to {{ stroke-dashoffset:0 }} }}
@keyframes otp-spin {{ to {{ transform:rotate(360deg) }} }}
@keyframes otp-shake {{ 0%,100% {{ transform:translateX(0) }} 20%,60% {{ transform:translateX(-7px) }} 40%,80% {{ transform:translateX(7px) }} }}
@keyframes otp-fade {{ from {{ opacity:0 }} to {{ opacity:1 }} }}
.otp-stage {{ position:relative; height:170px; display:grid; place-items:center; }}
.otp-fly {{ position:absolute; width:44px; height:52px; border-radius:12px; display:grid; place-items:center; font-weight:700; font-size:1.4rem; color:#fff;
  background:rgba(255,255,255,.07); border:1px solid rgba(224,177,58,.55); font-family:ui-monospace,Menlo,Consolas,monospace;
  animation: otp-scatter 1.6s ease-in-out forwards; box-shadow:0 0 16px rgba(224,177,58,.22); }}
.otp-check {{ position:absolute; width:76px; height:76px; border-radius:20px; display:grid; place-items:center; background:rgba(34,197,94,.12);
  border:2px solid {GREEN}; box-shadow:0 0 34px rgba(34,197,94,.4); opacity:0; animation: otp-pop .5s 1.45s ease-out forwards; }}
.otp-check svg path {{ stroke-dasharray:40; stroke-dashoffset:40; animation: otp-draw .45s 1.75s ease-out forwards; }}
.otp-ok h3 b {{ color:{GREEN}; }}
.otp-ok {{ animation: otp-fade .4s ease-out; }}
.otp-btn {{ display:flex; align-items:center; justify-content:center; gap:.5rem; border-radius:12px; padding:.62rem 1rem; font-weight:700; font-size:.9rem; }}
.otp-btn.busy {{ background:linear-gradient(180deg, {GOLD_2}, {GOLD}); color:#2a1d00; }}
.otp-btn.busy::before {{ content:""; width:15px; height:15px; border:2px solid rgba(42,29,0,.35); border-top-color:#2a1d00; border-radius:50%; animation: otp-spin .8s linear infinite; }}
.otp-btn.done {{ background:{GREEN}; color:#04210f; opacity:0; animation: otp-fade .3s 1.6s forwards; }}
.otp-shake {{ animation: otp-shake .45s; }}
</style>
"""

ICON_KEY = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="8" cy="15" r="4"/><path d="M10.8 12.2 20 3"/><path d="m16 7 3 3"/><path d="m14 9 2 2"/></svg>')
ICON_SHIELD = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
               '<path d="M12 3 4 6v6c0 5 3.4 8 8 9 4.6-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/></svg>')
ICON_CHECK = ('<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M5 12.5 10 17.5 19 7.5"/></svg>')

OFFSETS = [(-92, -46, -24), (30, -58, 18), (96, -22, 30), (-70, 48, -30), (22, 56, 22), (88, 40, -18)]


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def header(title_a: str, title_b: str, subtitle: str, *, icon: str = ICON_KEY, ok: bool = False):
    st.markdown(f'<div class="otp-head {"otp-ok" if ok else ""}"><div class="otp-key" '
                f'style="{"border-color:rgba(34,197,94,.5);color:#4ADE80;background:rgba(34,197,94,.10)" if ok else ""}">{icon}</div>'
                f'<h3>{html.escape(title_a)} <b>{html.escape(title_b)}</b></h3><p>{html.escape(subtitle)}</p></div>', unsafe_allow_html=True)


def cells(code: str):
    c = "".join(ch for ch in str(code or "") if ch.isdigit())[:CODE_LEN]
    st.markdown('<div class="otp-cells">' + "".join(
        f'<i class="{"on" if k < len(c) else ""}">{html.escape(c[k]) if k < len(c) else ""}</i>' for k in range(CODE_LEN)) + "</div>", unsafe_allow_html=True)


def success_animation(letters: str, *, verifying=("Vérification", "en cours…"), verifying_sub="Contrôle du code de sécurité", busy="Vérification du code…",
                      ok=("Vérifié", "avec succès"), ok_sub="Votre adresse e-mail est confirmée.", ok_btn="Vérifié et sécurisé", delay: float = 2.6):
    """Animation complète (≈2,6 s + 1,1 s) : lettres / chiffres qui tournent puis se rassemblent -> coche verte -> message de succès."""
    digits = str(letters)[:CODE_LEN].ljust(CODE_LEN, "•")
    fly = "".join(f'<div class="otp-fly" style="--dx:{dx}px;--dy:{dy}px;--rot:{rot}deg;animation-delay:{k * 0.06:.2f}s">{html.escape(digits[k])}</div>'
                  for k, (dx, dy, rot) in enumerate(OFFSETS))
    box = st.empty()
    box.markdown(f'<div class="otp-head"><div class="otp-key">{ICON_KEY}</div><h3>{html.escape(verifying[0])} <b>{html.escape(verifying[1])}</b></h3>'
                 f'<p>{html.escape(verifying_sub)}</p></div>'
                 f'<div class="otp-stage">{fly}<div class="otp-check">{ICON_CHECK}</div></div>'
                 f'<div class="otp-btn busy">{html.escape(busy)}</div>', unsafe_allow_html=True)
    time.sleep(delay)
    box.markdown(f'<div class="otp-head otp-ok"><div class="otp-key" style="border-color:rgba(34,197,94,.5);color:#4ADE80;background:rgba(34,197,94,.10)">{ICON_SHIELD}</div>'
                 f'<h3>{html.escape(ok[0])} <b>{html.escape(ok[1])}</b></h3><p>{html.escape(ok_sub)}</p></div>'
                 f'<div class="otp-stage"><div class="otp-check" style="opacity:1;animation:none">{ICON_CHECK}</div></div>'
                 f'<div class="otp-btn" style="background:{GREEN};color:#04210f">{html.escape(ok_btn)}</div>', unsafe_allow_html=True)
    time.sleep(1.1)


def verifying_then_verified(code: str, delay: float = 2.6):
    success_animation("".join(ch for ch in str(code) if ch.isdigit()), delay=delay)


AUTH_CSS = f"""
<style>
div.st-key-card_auth {{
  position:relative; overflow:hidden; border-radius:26px; padding:1.5rem 1.6rem 1.3rem;
  background:
    linear-gradient(115deg, transparent 18%, rgba(224,177,58,.10) 30%, transparent 42%),
    linear-gradient(65deg, transparent 52%, rgba(224,177,58,.16) 63%, transparent 72%),
    radial-gradient(120% 90% at 0% 0%, rgba(160,98,20,.38), transparent 55%),
    radial-gradient(110% 90% at 100% 100%, rgba(224,177,58,.20), transparent 55%),
    linear-gradient(160deg, #15110c 0%, #0b0a0a 60%, #14100a 100%) !important;
  border:1px solid rgba(245,210,122,.28) !important;
  box-shadow: 0 30px 70px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.10), inset 0 0 60px rgba(224,177,58,.05) !important;
}}
div.st-key-card_auth p, div.st-key-card_auth label, div.st-key-card_auth span {{ color:#F3EBDD; }}
div.st-key-card_auth [data-baseweb="tab-list"] {{ background:transparent !important; gap:.3rem; border-bottom:1px solid rgba(255,255,255,.10); }}
div.st-key-card_auth [data-baseweb="tab"] {{ color:rgba(243,235,221,.65) !important; background:transparent !important; }}
div.st-key-card_auth [data-baseweb="tab"][aria-selected="true"] {{ color:{GOLD_2} !important; }}
div.st-key-card_auth [data-baseweb="tab-highlight"] {{ background:{GOLD} !important; }}
div.st-key-card_auth [data-baseweb="input"], div.st-key-card_auth [data-baseweb="base-input"] {{
  background:rgba(255,255,255,.06) !important; border:1px solid rgba(255,255,255,.16) !important; border-radius:12px !important; }}
div.st-key-card_auth [data-baseweb="input"]:focus-within {{ border-color:rgba(224,177,58,.75) !important; box-shadow:0 0 0 2px rgba(224,177,58,.30), 0 0 22px rgba(224,177,58,.18) !important; }}
div.st-key-card_auth input {{ color:#fff !important; background:transparent !important; caret-color:{GOLD_2}; }}
div.st-key-card_auth [data-testid^="stBaseButton-primary"] {{
  background:linear-gradient(180deg, {GOLD_2}, {GOLD}) !important; border:none !important; border-radius:12px !important; box-shadow:0 8px 22px rgba(224,177,58,.28); }}
div.st-key-card_auth [data-testid^="stBaseButton-primary"] * {{ color:#2a1d00 !important; font-weight:700 !important; opacity:1 !important; }}
div.st-key-card_auth [data-testid^="stBaseButton-secondary"] {{ background:rgba(255,255,255,.06) !important; border:1px solid rgba(255,255,255,.16) !important; border-radius:12px !important; }}
div.st-key-card_auth [data-testid="stAlert"] {{ border-radius:12px; }}
</style>
"""


def inject_auth():
    st.markdown(AUTH_CSS, unsafe_allow_html=True)
