# -*- coding: utf-8 -*-
"""Procédures métier complètes, exécutées par les moteurs du site (règles + contrôles, sans IA) :
  ALSTOM EXPORT          -> FACTURES.xlsx + BL_REFERENCES_SUMMARY.xlsx (+ RECAP_DOUANE.xlsx) + compte rendu
  VENTILATION DOUANE     -> un classeur « Ventilation + Contrôle BL » par fournisseur + récapitulatif + ZIP + compte rendu (darija)
Aucune donnée n'est inventée ; chaque anomalie est signalée dans le compte rendu."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

REF_NAME_RE = re.compile(r"consolide|r[eé]f[eé]rentiel|referentiel|ref[_ -]?par|\bngp\b", re.I)


@dataclass
class WorkflowResult:
    kind: str                                   # "export" | "import"
    files: dict[str, bytes] = field(default_factory=dict)
    report: str = ""                            # compte rendu (markdown)
    kpis: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    checks: list[tuple[bool, str]] = field(default_factory=list)
    consensus: pd.DataFrame | None = None
    ok: bool = True


class _Up:
    """Fichier déposé, même interface que les uploads Streamlit."""
    def __init__(self, name: str, data: bytes):
        self.name, self._d = name, data

    def getvalue(self) -> bytes:
        return self._d


class _Progress:
    def __init__(self, cb=None):
        self.cb = cb

    def progress(self, v, text=""):
        if self.cb and text:
            self.cb(text)


def _fmt(v: float, d: int = 2) -> str:
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


# ============================================================================== EXPORT
def run_export(uploads: list[tuple[str, bytes]], progress=None, client_mode: str = "client") -> WorkflowResult:
    import core_export
    import export_engine as ee
    res = WorkflowResult("export")
    pdfs = [(n, d) for n, d in uploads]
    if not pdfs:
        res.ok = False
        res.report = "Aucun document : déposez les PDF (BL / packing lists + factures commerciales) du dossier, puis relancez **/alstom export**."
        return res
    r = ee.run_export_pipeline([_Up(n, d) for n, d in pdfs], core_export.OCREngine(), client_mode, _Progress(progress))
    fact_df = r["factures"].copy()
    bl_df = ee.normalize_bl_df(r["blref"])
    for c in ("Quantity", "Total Net Weight of the BL", "Total Gross Weight of the BL", "Number of Packages (Nombre de Colis)",
              "Prix unitaire total (Hors-taxe)"):
        bl_df[c] = pd.to_numeric(bl_df[c], errors="coerce")
    fact_df["Date de la facture"] = fact_df["Date de la facture"].map(ee._to_date)
    fb, bb = ee.build_factures_xlsx(fact_df), ee.build_bl_xlsx(bl_df)
    checks = ee.verify_files(fb, bb)
    rep = ee.build_report(fact_df, bl_df, r["notes"])
    res.files = {"FACTURES.xlsx": fb, "BL_REFERENCES_SUMMARY.xlsx": bb, "RECAP_DOUANE.xlsx": ee.build_recap_xlsx(fact_df, bl_df, rep)}
    res.files["Les_fichiers_+_compte_rendu.zip"] = ee.zip_files({**res.files, "COMPTE_RENDU.txt": ee.report_text(rep, checks).encode("utf-8")})
    res.checks, res.notes, res.consensus = checks, rep["notes"], r.get("consensus")
    res.kpis = {"Factures": rep["factures"], "BL uniques": rep["bl"], "Lignes articles": rep["lignes"], "Réf. distinctes": rep["refs_distinctes"],
                "Colis": f"{rep['colis']:g}", "Poids brut (kg)": _fmt(rep["poids_brut"], 3), "Poids net (kg)": _fmt(rep["poids_net"], 3),
                "Quantité": f"{rep['quantite']:g}"}
    for cur, v in rep["valeur_par_devise"].items():
        res.kpis[f"Valeur HT {cur or '?'}"] = _fmt(v)
    bad = [m for ok, m in checks if not ok]
    lines = [f"**{rep['factures']}** facture(s) · **{rep['bl']}** BL · **{rep['lignes']}** lignes d'articles "
             f"(références répétées : {rep['refs_repetees']} — chaque occurrence gardée sur sa propre ligne)."]
    lines.append("")
    lines.append("| | |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in res.kpis.items()))
    lines.append("")
    lines.append("**Contrôles des fichiers :** " + ("tous OK ✔" if not bad else "; ".join("⚠ " + m for m in bad)))
    real = [n for n in rep["notes"] if not n.startswith(("Moteur", "Facture ")) or "⚠" in n]
    real = [n for n in real if "montant pris sur" not in n and "lue deux fois" not in n]
    if real:
        lines.append("\n**Points à vérifier :**\n" + "\n".join(f"- {n}" for n in real[:15]))
    res.report = "\n".join(lines)
    res.ok = not bad
    return res


# ============================================================================== IMPORT
def split_import_uploads(uploads: list[tuple[str, bytes]]):
    """-> (documents, fichier de référence NGP ou None) : CONSOLIDE_CLIENTS / référentiel reconnu par son nom (xlsx / csv)."""
    docs, ref = [], None
    for n, d in uploads:
        if ref is None and n.lower().endswith((".xlsx", ".xlsm", ".xls", ".csv")) and REF_NAME_RE.search(n):
            ref = _Up(n, d)
        else:
            docs.append(_Up(n, d))
    return docs, ref


def run_import(uploads: list[tuple[str, bytes]], progress=None, merge_suppliers: bool = False) -> WorkflowResult:
    import app as core
    import import_consensus
    import referentiel_store
    import ventilation_douane as vd
    res = WorkflowResult("import")
    docs, ref = split_import_uploads(uploads)
    if not docs:
        res.ok = False
        res.report = ("Aucun document : déposez l'avis d'arrivée, les factures, les BL / DDT / packing lists (et le CONSOLIDE_CLIENTS si mis à jour), "
                      "puis relancez **/ventilation douane alstom**.")
        return res
    prog = _Progress(progress)
    result = core.run_pipeline(docs, ref, core.OCREngine(), "Valeur HT", prog, None)
    lines, man = result["lines"], result["manifest"]
    if lines is None or lines.empty:
        res.ok = False
        res.report = "Aucune ligne de facture lue dans ces documents : vérifiez les fichiers (scans illisibles ?)."
        res.notes = [str(m) for m in result.get("log", [])][:8]
        return res
    c_notes = []
    try:
        lines, c_notes, res.consensus = import_consensus.analyse(lines, man, result.get("inv_totals"))
    except Exception as exc:  # noqa: BLE001
        c_notes = [f"⚠ Contrôle multi-méthodes indisponible ({type(exc).__name__})."]
    final = core.apply_matching(lines, result["refdb"])
    names = list(dict.fromkeys(str(v or "").strip() or "(sans nom)" for v in final["Client"]))
    out = vd.build_all(final, man if man is not None and len(man) else None, None, [names] if merge_suppliers and len(names) > 1 else None)
    res.files = {**out["files"], **({"RECAP_CONSOLIDE.xlsx": out["recap"]} if out.get("recap") else {}), "Tous_les_fichiers.zip": out["zip"]}
    stats = out["stats"]
    refdb = result.get("refdb") or {}
    # --- compte rendu (darija) : tableau des totaux + Ntebh
    tbl = ["| Fournisseur | Lignes | Qté | Poids net (kg) | Poids brut (kg) | Total HT | Avis d'arrivée |", "|---|---|---|---|---|---|---|"]
    ntebh = []
    for s in stats:
        avis = f"{_fmt(s['avis_valeur'])} {s['devise']}" if s.get("avis_valeur") else "—"
        tbl.append(f"| {s['supplier']} | {s['lignes']} | {s['qté']:g} | {_fmt(s['net'], 3)} | {_fmt(s['brut'], 3)} | {_fmt(s['ht'] + s['frais'])} {s['devise']} | {avis} |")
        ntebh += [f"**{s['supplier']}** — {f}" for f in s.get("flags", [])]
        if s.get("avis_valeur") and abs(s["ht"] + s["frais"] - s["avis_valeur"]) > 0.05:
            ntebh.append(f"**{s['supplier']}** — Ntebh : total HT {_fmt(s['ht'] + s['frais'])} ≠ GOODS VALUE de l'avis {_fmt(s['avis_valeur'])} (écart {_fmt(s['ht'] + s['frais'] - s['avis_valeur'])}).")
        if s.get("avis_brut") and abs(s["brut"] - s["avis_brut"]) > max(0.5, 0.005 * s["avis_brut"]):
            ntebh.append(f"**{s['supplier']}** — Ntebh : poids brut lignes {_fmt(s['brut'], 3)} ≠ avis {_fmt(s['avis_brut'], 3)} kg.")
    ntebh += [n for n in c_notes if n.startswith("⚠")]
    if refdb.get("source"):
        ntebh.insert(0, f"Référentiel NGP utilisé : « {refdb['source']} » ({refdb.get('count', 0)} références)."
                     + ("" if ref is not None else " (dernier référentiel enregistré — joignez le CONSOLIDE_CLIENTS à jour si besoin)"))
    elif not refdb.get("count"):
        ntebh.insert(0, "Ntebh : aucun référentiel NGP (CONSOLIDE_CLIENTS) : toutes les lignes sont « A VERIFIER ». Joignez le fichier à jour puis relancez.")
    res.kpis = {"Fournisseurs": len(stats), "Lignes": sum(s["lignes"] for s in stats), "Qté": f"{sum(s['qté'] for s in stats):g}",
                "Poids net (kg)": _fmt(sum(s["net"] for s in stats), 3), "Poids brut (kg)": _fmt(sum(s["brut"] for s in stats), 3)}
    for cur in dict.fromkeys(s["devise"] for s in stats):
        res.kpis[f"Total HT {cur}"] = _fmt(sum(s["ht"] + s["frais"] for s in stats if s["devise"] == cur))
    res.notes = ntebh
    res.report = ("Sf wjd. Hna l-natija:\n\n" + "\n".join(tbl) + ("\n\n**Ntebh :**\n" + "\n".join(f"- {n}" for n in ntebh[:20]) if ntebh else "\n\nKolchi mrbout m3a l-avis d'arrivée ✔")
                  + ("\n\n_Les fournisseurs ont été mis dans le même tableau (fnefs tableau)._" if merge_suppliers and len(names) > 1 else ""))
    return res
