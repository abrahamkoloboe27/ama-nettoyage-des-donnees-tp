"""Tests qualité de la slide 31 (et volumétrie), utilisés par le suivi des indicateurs et le tableau de bord."""
import pandas as pd

from .config import DEBUT, FIN, STATUTS_OK, VILLES
from .kpis import calculer_kpis

# ---------------------------------------------------------------- tests qualité (slide 31)
TESTS = {
    "commande_id unique":        lambda d: d["commande_id"].is_unique,
    "clés jamais vides":         lambda d: d[["commande_id", "date_commande", "montant_fcfa"]].notna().all().all(),
    "statut connu":              lambda d: d["statut"].isin(STATUTS_OK).all(),
    "ville du référentiel":      lambda d: d["ville"].dropna().isin(set(VILLES.values())).all(),
    "note entre 1 et 5":         lambda d: d["note_client"].dropna().between(1, 5).all(),
    "livraison après commande":  lambda d: not (d["date_livraison"] < d["date_commande"]).any(),
    "montant = quantité × prix": lambda d: ((d["montant_fcfa"].abs() - d["quantite"] * d["prix_unitaire_fcfa"]).abs()
                                           <= 0.3 * d["quantite"] * d["prix_unitaire_fcfa"]).all(),
    "commandes de septembre":    lambda d: d["date_commande"].dropna().between(DEBUT, FIN, inclusive="left").all(),
}
NOMS_TESTS = list(TESTS)
NOM_VOLUMETRIE = "volumétrie (≥ 95 % des 50 000 commandes)"


def tests_qualite(df):
    """Les 8 tests de la slide 31 et la volumétrie ; un test qui plante compte comme un échec."""
    resultats = {}
    for nom, test in TESTS.items():
        try:
            resultats[nom] = bool(test(df))
        except Exception:
            resultats[nom] = False
    try:
        resultats[NOM_VOLUMETRIE] = bool(df["commande_id"].nunique() >= 0.95 * 50_000)
    except Exception:
        resultats[NOM_VOLUMETRIE] = False
    return pd.Series(resultats)


def kpis_et_tests(df):
    """Indicateurs métier + nombre de tests qualité réussis (sur 8) + volumétrie."""
    t = tests_qualite(df)
    return {**calculer_kpis(df), "tests_qualite": int(t[NOMS_TESTS].sum()), "volumetrie": bool(t[NOM_VOLUMETRIE])}
