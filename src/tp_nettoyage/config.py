"""Chemins, constantes et couleurs du TD « Nettoyage des données » (module 13, AMA)."""
import os
from pathlib import Path

import pandas as pd


def _trouver_racine():
    """Remonte l'arborescence jusqu'au dossier qui contient data/raw/commandes_brutes.csv.

    La variable d'environnement TP_NETTOYAGE_RACINE, si elle existe, impose ce dossier (tests, correction).
    """
    if os.environ.get("TP_NETTOYAGE_RACINE"):
        return Path(os.environ["TP_NETTOYAGE_RACINE"]).resolve()
    departs = [Path.cwd().resolve(), Path(__file__).resolve().parent]
    for depart in departs:
        for dossier in [depart, *depart.parents]:
            if (dossier / "data" / "raw" / "commandes_brutes.csv").exists():
                return dossier
    return Path.cwd().resolve()


RACINE = _trouver_racine()
BRUT = RACINE / "data" / "raw" / "commandes_brutes.csv"
ORACLE = RACINE / "data" / "oracle" / "note_vraie.csv"
SORTIES_DIR = RACINE / "output"
SCENARIOS_DIR = SORTIES_DIR / "scenarios"
RAPPORTS_DIR = SORTIES_DIR
SHA256_BRUT = "c6e44276567e9b3326dcb10e7adce56f5b38486e3352c8957181f34f8e0606a9"

TZ = "Africa/Porto-Novo"                                   # Cotonou, UTC+1
DEBUT, FIN = pd.Timestamp("2026-09-01", tz=TZ), pd.Timestamp("2026-10-01", tz=TZ)

# Référentiel des villes (slide 15) : fourni, car il sert aussi aux tests qualité.
VILLES = {"cotonou": "Cotonou", "ctn": "Cotonou", "cotonu": "Cotonou",
          "abomey-calavi": "Abomey-Calavi", "abomey calavi": "Abomey-Calavi", "calavi": "Abomey-Calavi",
          "porto-novo": "Porto-Novo", "porto novo": "Porto-Novo", "parakou": "Parakou", "bohicon": "Bohicon"}
STATUTS_OK = ["livrée", "annulée", "en cours", "retournée"]

# Charte AMA (identique au deck du cours)
COULEURS = {
    "marine": "#003060",
    "bleu": "#0B4F9C",
    "bleu_clair": "#E8F1FB",
    "texte": "#1F2937",
    "gris": "#4B5563",
    "types": "#2E86DE",
    "doublons": "#7B4FBF",
    "aberrantes": "#D64545",
    "manquants": "#E8A33D",
    "qualite": "#2E9E6B",
}
