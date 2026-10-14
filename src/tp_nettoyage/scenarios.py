"""Les scénarios de décisions de nettoyage, et le fichier qui les réunit tous."""
from pathlib import Path

import pandas as pd

from .config import SCENARIOS_DIR

SCENARIOS = {
    "0_brut_type":          dict(formats=False, doublons=False, aberrantes="aucune", manquants="aucune"),
    "1_recommande":         dict(),
    "2_doublons_gardes":    dict(doublons=False),
    "3_aberrantes_iqr":     dict(aberrantes="iqr_suppression"),
    "4_manquants_dropna":   dict(manquants="dropna"),
    "5_manquants_zero":     dict(manquants="zero"),
    "6_fuseau_utc":         dict(fuseau="UTC"),
    "7_imputation_moyenne": dict(manquants="moyenne"),
}

LIBELLES_SCENARIOS = {
    "0_brut_type":          "Brut, types convertis",
    "1_recommande":         "Recommandé (le cours)",
    "2_doublons_gardes":    "Doublons gardés",
    "3_aberrantes_iqr":     "Aberrantes supprimées à l'IQR",
    "4_manquants_dropna":   "dropna() global",
    "5_manquants_zero":     "NaN remplacés par 0",
    "6_fuseau_utc":         "Dates laissées en UTC",
    "7_imputation_moyenne": "Imputation par la moyenne",
}

OBLIGATOIRES = list(SCENARIOS)[:6]
BONUS = list(SCENARIOS)[6:]
FICHIER_CONSOLIDE = "tous_les_scenarios.parquet"


def harmoniser(frames):
    """Empile les scénarios dans un seul DataFrame au schéma commun (colonne « scenario »)."""
    drapeaux = ["double_clic", "gros_volume", "a_email", "poids_impute"]
    sortie = []
    for nom, d in frames.items():
        d = d.copy()
        for col in drapeaux:
            d[col] = d[col].astype("boolean") if col in d else pd.Series(pd.NA, index=d.index, dtype="boolean")
        for col in ["ville", "categorie"]:
            d[col] = d[col].astype("str")
        d.insert(0, "fuseau", str(d["date_commande"].dt.tz))      # pour relire chaque scénario dans son fuseau
        for col in ["date_commande", "date_livraison", "maj_le"]:
            d[col] = d[col].dt.tz_convert("UTC")
        d.insert(0, "scenario", nom)
        sortie.append(d)
    return pd.concat(sortie, ignore_index=True)


def separer(tous):
    """Inverse de harmoniser : un DataFrame par scénario, dates remises dans leur fuseau.

    Les indicateurs sont identiques à ceux des scénarios d'origine ; ville et categorie restent en texte et les
    drapeaux absents d'un scénario y sont des colonnes vides (<NA>).
    """
    frames = {}
    for nom, d in tous.groupby("scenario", sort=True):
        d = d.drop(columns="scenario").reset_index(drop=True)
        fuseau = d["fuseau"].iloc[0]
        for col in ["date_commande", "date_livraison", "maj_le"]:
            d[col] = d[col].dt.tz_convert(fuseau)
        frames[nom] = d.drop(columns="fuseau")
    return frames


def charger_scenarios(dossier=SCENARIOS_DIR):
    """Lit le fichier consolidé s'il existe, sinon chaque <scénario>.parquet du dossier ; {} si rien n'est trouvé."""
    dossier = Path(dossier)
    consolide = dossier / FICHIER_CONSOLIDE
    if consolide.exists():
        return separer(pd.read_parquet(consolide))
    frames = {}
    for chemin in sorted(dossier.glob("*.parquet")):
        if chemin.name != FICHIER_CONSOLIDE:
            frames[chemin.stem] = pd.read_parquet(chemin)
    return frames
