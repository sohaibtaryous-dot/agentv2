# -*- coding: utf-8 -*-
"""Module ASSISTANT — conversation pour générer / modifier des fichiers Excel et PDF (agents IA + contrôle qualité)."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

import ui
from agents import orchestrator, skills, workflows
from utils import files as F
from utils.config import get_secret
from utils import llm as L

K_MSGS, K_DELIV, K_SPECS, K_UP, K_WF = "asst_msgs", "asst_deliv", "asst_specs", "asst_uploads", "asst_wf"
EXAMPLES = ["/alstom export — extraction BL + factures (PDF déposés) → FACTURES.xlsx + BL_REFERENCES_SUMMARY.xlsx",
            "/ventilation douane alstom — ventilation de l'import (avis d'arrivée, factures, DDT, + CONSOLIDE_CLIENTS)",
            "/ventilation douane alstom fnefs tableau — tous les fournisseurs dans le même tableau","Fais un tableau Excel des factures avec total et TVA 20 % en formules.",
            "Génère un rapport PDF de ce dossier avec un tableau récapitulatif.",
            "Ajoute une colonne « Écart » et colore l'en-tête en vert."]


def _history(msgs: list[dict], n: int = 6) -> str:
    return "\n".join(f"{'Utilisateur' if m['role'] == 'user' else 'Assistant'} : {m['content']}" for m in msgs[-n:])


def _preview_excel(d: orchestrator.Deliverable):
    calc = F.recalc_xlsx(d.data) if F.libreoffice_path() else None
    src = calc or d.data
    xl = pd.ExcelFile(io.BytesIO(src))
    tabs = st.tabs(xl.sheet_names[:8])
    for tab, name in zip(tabs, xl.sheet_names[:8]):
        with tab:
            st.dataframe(xl.parse(name, dtype=object).fillna("").astype(str), use_container_width=True, hide_index=True)
    if not calc:
        st.caption("Aperçu : valeurs saisies ; les formules se calculent à l'ouverture dans Excel.")


def _preview_pdf(d: orchestrator.Deliverable):
    png = F.pdf_first_page_png(d.data)
    if png:
        st.image(png, caption="Aperçu — page 1", use_container_width=True)


def _render_deliverable(d: orchestrator.Deliverable, i: int):
    icon = ":material/table_view:" if d.kind == "excel" else ":material/picture_as_pdf:"
    with st.container(border=True):
        st.markdown(f"**{d.filename}**")
        if d.validated:
            st.success(f"Contrôle qualité réussi ({d.attempts} essai{'s' if d.attempts > 1 else ''}).", icon=":material/verified:")
            (_preview_excel if d.kind == "excel" else _preview_pdf)(d)
            st.download_button(f"Télécharger {d.filename}", d.data, file_name=d.filename, icon=icon, type="primary", key=f"asst_dl_{i}",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if d.kind == "excel" else "application/pdf",
                               use_container_width=True)
        else:
            if d.data:
                st.error("Le fichier n'a pas passé le contrôle qualité : il n'est pas proposé au téléchargement.", icon=":material/gpp_bad:")
            else:
                st.warning("Fichier non généré.", icon=":material/info:")
            for e in d.errors[:8]:
                st.markdown(f"- {e}")
            st.caption("Reformulez votre demande ou précisez les données, puis réessayez.")
        with st.expander("Journal du contrôle qualité"):
            for line in d.qa_log:
                st.markdown(f"- {line}")


def _render_workflow(wf: workflows.WorkflowResult):
    title = "ALSTOM EXPORT — FACTURES + BL_REFERENCES_SUMMARY" if wf.kind == "export" else "VENTILATION DOUANE ALSTOM"
    with st.container(border=True):
        st.markdown(f"**{title}**")
        (st.success if wf.ok else st.warning)("Procédure terminée." if wf.ok else "Procédure terminée avec des points à vérifier / un blocage.",
                                               icon=":material/verified:" if wf.ok else ":material/warning:")
        if wf.kpis:
            items = list(wf.kpis.items())
            for i in range(0, len(items), 3):
                cols = st.columns(3)
                for c, (k, v) in zip(cols, items[i:i + 3]):
                    c.metric(k, v)
        st.markdown(wf.report)
        for j, (name, data) in enumerate(wf.files.items()):
            if name.endswith(".zip"):
                mime, kind = "application/zip", "secondary"
            else:
                mime, kind = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "primary"
            st.download_button(f"Télécharger {name}", data, file_name=name, mime=mime, type=kind, key=f"asst_wf_{wf.kind}_{j}",
                               icon=":material/folder_zip:" if name.endswith(".zip") else ":material/table_view:", use_container_width=True)
        if wf.consensus is not None and len(wf.consensus):
            with st.expander("Calcul multi-méthodes (vote)"):
                st.dataframe(wf.consensus.dropna(axis=1, how="all").astype(object).where(lambda x: x.notna(), "").astype(str), use_container_width=True, hide_index=True)


def render(ai_cfg):
    ui.hero_3d({"agents": 4, "formats": "Excel · PDF", "contrôle": "QA auto", "essais": orchestrator.MAX_TRIES},
               badge="TIMAR TANGER · ASSISTANT", title="Assistant fichiers", highlight="Excel & PDF",
               desc="Décrivez le fichier voulu (ou déposez vos données) : les agents extraient, génèrent, puis un contrôle qualité "
                    "corrige automatiquement avant le téléchargement.", ai_label="")
    gem_secret = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")
    claude_ok = L.LLM(ai_cfg).available
    engines = ["Local — sans clé (commandes simples)", "Gemini — clé GRATUITE (comprend tout)"] + (["Claude — clé Anthropic"] if claude_ok else [])
    default = 1 if gem_secret else (2 if claude_ok else 0)
    engine = st.radio("Moteur", engines, index=default, horizontal=True, key="asst_engine")
    llm = None
    if engine.startswith("Gemini"):
        c1, c2 = st.columns([2, 1])
        gem_key = c1.text_input("Clé Gemini (gratuite)", type="password", value="", placeholder="AIza… (ou GEMINI_API_KEY dans les Secrets)",
                                key="asst_gem_key", help="Gratuite, sans carte bancaire : aistudio.google.com → « Get API key ».").strip() or gem_secret
        gem_model = c2.selectbox("Modèle", L.GEMINI_MODELS, key="asst_gem_model")
        if gem_key:
            llm = L.LLM(gemini_key=gem_key, gemini_model=gem_model)
        else:
            st.info("Pour que l'agent comprenne n'importe quelle demande, collez une clé Gemini **gratuite** : "
                    "[aistudio.google.com/apikey](https://aistudio.google.com/apikey) → « Create API key » (1 minute, sans carte bancaire).",
                    icon=":material/key:")
    elif engine.startswith("Claude"):
        llm = L.LLM(ai_cfg)
    if llm is None:
        st.info("**Moteur local (sans clé API)** : déposez vos données (Excel, CSV, ou PDF de BL / factures) puis demandez, par exemple : "
                "« tableau Excel avec total et TVA 20 % », « trié par Montant, récapitulatif par Client, en-tête vert », "
                "« rapport PDF », puis « ajoute une colonne écart », « supprime la colonne Date », « renomme X en Y ». "
                "Procédures complètes (sans clé) : **/alstom export** et **/ventilation douane alstom**.", icon=":material/smart_toy:")
    st.session_state.setdefault(K_MSGS, [])
    st.session_state.setdefault(K_DELIV, [])
    st.session_state.setdefault(K_SPECS, {})
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        up = st.file_uploader("Données (optionnel) : Excel, CSV, PDF, Word, texte", accept_multiple_files=True, key="asst_files",
                              type=["xlsx", "xlsm", "xls", "csv", "pdf", "docx", "txt"])
        box = st.container(height=470, border=True)
        with box:
            if not st.session_state[K_MSGS]:
                st.caption("Exemples de demandes :")
                for e in EXAMPLES:
                    st.markdown(f"- {e}")
            for m in st.session_state[K_MSGS]:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])
        prompt = st.chat_input("Décrivez le fichier à créer ou la modification à faire…")
        if st.session_state[K_MSGS] and st.button("Nouvelle conversation", icon=":material/restart_alt:", key="asst_reset"):
            for k in (K_MSGS, K_DELIV, K_SPECS, K_WF):
                st.session_state.pop(k, None)
            st.rerun()
    if prompt:
        st.session_state[K_MSGS].append({"role": "user", "content": prompt})
        uploads = [(f.name, f.getvalue()) for f in (up or [])]
        flow = skills.detect_workflow(prompt)                  # « /alstom export », « /ventilation douane alstom »…
        merge = bool(skills.MERGE_RE.search(prompt))
        if flow is None and llm is not None:                   # avec un modèle IA : n'importe quelle formulation est comprise
            rt = skills.route(llm, prompt, _history(st.session_state[K_MSGS][:-1]), bool(uploads))
            flow = {"export_workflow": "export", "import_workflow": "import"}.get(rt.get("intent"))
            merge = merge or bool(rt.get("merge_suppliers"))
            if rt.get("intent") == "answer" and rt.get("answer_text"):
                st.session_state[K_MSGS].append({"role": "assistant", "content": rt["answer_text"]})
                st.rerun()
        if flow:
            status = left.empty()
            try:
                wf = (workflows.run_export(uploads, lambda t: status.info(t, icon=":material/smart_toy:")) if flow == "export"
                      else workflows.run_import(uploads, lambda t: status.info(t, icon=":material/smart_toy:"), merge_suppliers=merge))
                status.empty()
                st.session_state[K_WF] = wf
                head = "Procédure ALSTOM EXPORT" if flow == "export" else "Procédure VENTILATION DOUANE ALSTOM"
                st.session_state[K_MSGS].append({"role": "assistant", "content": f"{head} exécutée — tableau des totaux, points à vérifier (Ntebh) et fichiers à télécharger à droite."
                                                                     + ("" if wf.ok else "\n\n⚠ Des points sont à vérifier : voir le compte rendu.")})
            except Exception as exc:  # noqa: BLE001
                status.empty()
                st.session_state[K_MSGS].append({"role": "assistant", "content": f"Erreur pendant la procédure : {type(exc).__name__}: {exc}"})
            st.rerun()
        sig = tuple((n, len(d)) for n, d in uploads)
        same_files = bool(st.session_state[K_SPECS]) and sig == st.session_state.get("asst_up_sig")
        st.session_state["asst_up_sig"] = sig
        if same_files and llm is None:                         # mêmes fichiers qu'avant : le moteur local MODIFIE le fichier précédent
            uploads = []
        status = left.empty()
        try:
            res = orchestrator.run(prompt, uploads, llm, previous=st.session_state[K_SPECS], history=_history(st.session_state[K_MSGS][:-1]),
                                   progress=lambda t: status.info(t, icon=":material/smart_toy:"))
            status.empty()
            st.session_state[K_DELIV] = res.deliverables
            for d in res.deliverables:
                if d.validated:
                    st.session_state[K_SPECS][d.kind] = d.spec
            ok = [d for d in res.deliverables if d.validated]
            msg = (f"Fichier(s) prêt(s) : {', '.join(d.filename for d in ok)}." if ok else "Je n'ai pas réussi à produire un fichier valide.")
            for d in res.deliverables:
                if not d.validated and d.errors:
                    msg += f"\n\n**{d.filename}** : {d.errors[0]}"
            if res.notes:
                msg += "\n\n" + "\n".join(f"⚠ {n}" for n in res.notes)
            st.session_state[K_MSGS].append({"role": "assistant", "content": msg})
        except L.LLMError as exc:
            status.empty()
            st.session_state[K_MSGS].append({"role": "assistant", "content": f"Erreur : {exc}"})
        st.rerun()
    with right:
        ui.section("Aperçu & téléchargement", "download")
        dels = st.session_state[K_DELIV]
        if st.session_state.get(K_WF) is not None:
            _render_workflow(st.session_state[K_WF])
        if not dels and st.session_state.get(K_WF) is None:
            st.info("Le fichier généré apparaîtra ici avec son aperçu ; le bouton de téléchargement n'apparaît qu'après validation.")
        for i, d in enumerate(dels):
            _render_deliverable(d, i)
