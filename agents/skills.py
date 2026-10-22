# -*- coding: utf-8 -*-
"""Connaissance métier de l'assistant : les 2 procédures « ALSTOM EXPORT » et « VENTILATION DOUANE ALSTOM » (résumé des règles),
détection de la procédure demandée, et routage d'une demande libre (avec un modèle IA) vers la bonne action."""

from __future__ import annotations

import re

SKILL_EXPORT = """PROCÉDURE « ALSTOM EXPORT » — extraction PDF BL / Packing List + Factures commerciales -> 2 fichiers Excel.
- Toujours 2 fichiers .xlsx distincts : FACTURES.xlsx (1 feuille « Factures », 5 colonnes : Numéro de facture, Nom du fournisseur ou client,
  Date de la facture, Devise, Montant en devise ; 1 ligne par facture ; numéro en texte ; vraie date JJ/MM/AAAA ; devise 3 lettres ;
  montant numérique 0.00 = total HT ; aucune ligne de total, aucune fusion) et BL_REFERENCES_SUMMARY.xlsx (3 feuilles : BL References,
  BL SUMMARY, GLOBAL TOTAL).
- BL References : 11 colonnes (Reference, Description, Quantity, Unit, BL Number, Invoice Number, Total Net Weight of the BL, Total Gross Weight of the BL,
  Number of Packages, Prix unitaire total (Hors-taxe), Customer PO). UNE LIGNE SOURCE = UNE LIGNE EXCEL : une référence répétée reste sur des lignes
  séparées, jamais fusionnée / additionnée / supprimée. Poids net, brut et colis du BL : une seule fois, sur la 1re ligne du BL. Une couleur par BL.
- Quantité = celle des factures. Prix = montant HT de chaque ligne. Customer PO exact. Rien d'inventé : donnée absente = cellule vide + signalement.
- BL SUMMARY : 1 ligne par BL (quantité, poids net, poids brut, colis, valeur HT). GLOBAL TOTAL : COLIS, POIDS BRUT, POIDS NET, VALEUR DEVISE, QUANTITE
  (devises jamais additionnées entre elles).
- Contrôles : nombre de lignes source = lignes Excel, quantités BL vs facture, somme des lignes = total HT facture, poids / colis une seule fois par BL.
- Compte rendu final : nb factures, BL, lignes, références distinctes / répétées, colis, poids brut / net, valeur HT par devise, quantité, anomalies."""

SKILL_IMPORT = """PROCÉDURE « VENTILATION DOUANE ALSTOM » (Alstom Railways Maroc, Fès) — 1 tableau Excel par expédition / fournisseur.
- Documents : avis d'arrivée TIMAR (n° SXVF…, GOODS VALUE = total de référence, poids brut, colis), factures, BL / DDT / packing lists,
  référentiel CONSOLIDE_CLIENTS (NGP par référence, à jour à chaque lot).
- Règle absolue : ne jamais fusionner les références répétées (chaque occurrence = sa ligne).
- NGP : cherché dans le référentiel (références composées « A-B » : chaque partie ; coquille d'un caractère signalée). Si le NGP du référentiel
  diffère du code HS de la facture : NGP du référentiel + HS facture conservé + alerte « Ntebh ». Introuvable : « A VERIFIER ».
- Poids : ceux des documents ; sinon estimés au prorata (valeur HT, ou quantité), en-têtes jaune foncé + commentaire. Colonnes net (g unitaire, g total, kg) et brut (kg).
- Frais administratifs : répartis au prorata du HT ; colonnes « Frais administratifs ventilés » et « Total HT + frais ».
- Classeur : feuille « Ventilation » (~20 colonnes, formules vivantes, TOTAL en SUBTOTAL, couleur par BL) + feuille « Contrôle BL » (écarts poids / HT,
  rapprochement avec l'avis d'arrivée, notes d'anomalies « Ntebh »). Valeur et poids doivent coller à l'avis d'arrivée.
- « FNEFS TABLEAU » = ajouter au tableau d'un fournisseur ; par défaut un fichier séparé par expédition. Récapitulatif consolidé sur demande."""

EXPORT_RE = re.compile(r"alstom[\s_-]*export|export[\s_-]*alstom|factures?\.xlsx|bl[_ ]references|references[_ ]summary|export\s+bl\s*(?:&|et)\s*factures?", re.I)
IMPORT_RE = re.compile(r"ventilation[\s_-]*(?:de\s+)?douane|ventilation\s+alstom|alstom\s+ventilation|hada\s+f[ea]?\s*tableau\s+excel|tableau\s+excel\s+bohdo|"
                       r"consolide[_ ]clients|fnefs\s+tableau|f\s*nefs\s+tableau|\bdouane\s+alstom|alstom\s+douane", re.I)
MERGE_RE = re.compile(r"f\s*nefs\s+tableau|fnefs\s+tableau|nefs\s+tableau|m[eê]me\s+tableau|same\s+table|zid\s+hado", re.I)


def detect_workflow(request: str) -> str | None:
    """« /alstom export », « /ventilation douane alstom », mots clés équivalents -> 'export' | 'import' | None."""
    r = request or ""
    e, i = bool(EXPORT_RE.search(r)), bool(IMPORT_RE.search(r))
    if i and not e:
        return "import"
    if e and not i:
        return "export"
    return None


ROUTER_SYSTEM = f"""Tu es le routeur de l'assistant TIMAR (transit / douane, Alstom). Tu comprends le français, l'anglais et la darija marocaine
écrite en lettres latines. Choisis l'action qui correspond à la demande de l'utilisateur :
- "export_workflow" : il veut extraire / traiter des BL, packing lists et factures commerciales d'un dossier d'EXPORT (FACTURES.xlsx + BL_REFERENCES_SUMMARY.xlsx).
- "import_workflow" : il veut la ventilation douane d'un dossier d'IMPORT (avis d'arrivée, factures fournisseur, DDT, NGP) = un tableau Excel de ventilation.
- "make_file" : il veut créer / modifier un autre fichier Excel ou PDF (tableau, rapport, calcul…).
- "answer" : c'est une question, une explication, une aide sur les règles ou le fonctionnement : réponds dans "answer_text" (même langue que lui, court et précis).
Pour "import_workflow", mets merge_suppliers=true s'il demande d'ajouter / mettre les fournisseurs dans le même tableau (« fnefs tableau »).

CONNAISSANCE MÉTIER :
{SKILL_EXPORT}

{SKILL_IMPORT}"""

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {"intent": {"type": "string", "enum": ["export_workflow", "import_workflow", "make_file", "answer"]},
                   "answer_text": {"type": "string"}, "merge_suppliers": {"type": "boolean"}},
    "required": ["intent"],
}


def route(llm, request: str, history: str = "", has_files: bool = False) -> dict:
    """Avec un modèle IA : comprend n'importe quelle formulation. Renvoie {"intent", "answer_text", "merge_suppliers"}."""
    user = (f"Historique :\n{history}\n\n" if history else "") + f"Fichiers déposés : {'oui' if has_files else 'non'}\nDemande : {request}"
    try:
        out = llm.structured(ROUTER_SYSTEM, user, ROUTER_SCHEMA, "route", max_tokens=1500)
        if out.get("intent") in ROUTER_SCHEMA["properties"]["intent"]["enum"]:
            return out
    except Exception:  # noqa: BLE001  (routeur indisponible : on retombe sur la génération de fichier)
        pass
    return {"intent": "make_file"}
