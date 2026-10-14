"""Indicateurs métier du TP : calcul, libellés, comparaison entre scénarios, format français."""
import math

import numpy as np
import pandas as pd

ESPACE_FINE = " "


def calculer_kpis(df):
    """Indicateurs métier ; un indicateur incalculable (mauvais type) vaut NaN au lieu de planter."""
    def essai(f):
        try:
            return f()
        except Exception:
            return np.nan

    try:
        livrees = df[df["statut"] == "livrée"]
        if "double_clic" in df.columns:                      # doubles clics : remboursés, hors CA
            livrees = livrees[~livrees["double_clic"].astype("boolean").fillna(False)]
    except Exception:                                        # colonne absente ou illisible : aucune livrée
        livrees = df.iloc[0:0]

    def reachat():
        n = livrees["client_id"].value_counts()
        return float((n >= 2).mean() * 100)

    def retention():
        jour = livrees["date_commande"].dt.day
        s1 = set(livrees.loc[jour <= 7, "client_id"])
        apres = set(livrees.loc[jour >= 8, "client_id"])
        return len(s1 & apres) / len(s1) * 100

    def meilleur_jour():
        ca_jour = livrees.groupby(livrees["date_commande"].dt.date)["montant_fcfa"].sum()
        return str(ca_jour.idxmax())

    ca = essai(lambda: float(livrees["montant_fcfa"].sum()))

    def part_du_ca(masque):
        if not ca or math.isnan(ca):                         # pas de CA : part incalculable
            return np.nan
        return float(livrees.loc[masque, "montant_fcfa"].sum() / ca * 100)

    return {
        "lignes": len(df),
        "commandes_livrees": len(livrees),
        "ca_fcfa": ca,
        "panier_moyen_fcfa": essai(lambda: float(livrees["montant_fcfa"].mean())),
        "prix_moyen_fcfa": essai(lambda: float(df["prix_unitaire_fcfa"].astype(float).mean())),
        "clients_actifs": essai(lambda: livrees["client_id"].nunique()),
        "clients_par_telephone": essai(lambda: livrees["telephone"].nunique()),
        "taux_reachat_pct": essai(reachat),
        "retention_s1_pct": essai(retention),
        "note_moyenne": essai(lambda: float(df["note_client"].mean())),
        "delai_moyen_j": essai(lambda: float((livrees["date_livraison"] - livrees["date_commande"]).dt.total_seconds().mean() / 86400)),
        "part_mobile_money_pct": essai(lambda: float((df["moyen_paiement"] == "Mobile Money").mean() * 100)),
        "part_ca_cotonou_pct": essai(lambda: part_du_ca(livrees["ville"] == "Cotonou")),
        "taux_annulation_pct": essai(lambda: float((df["statut"] == "annulée").mean() * 100)),
        "part_insatisfaits_pct": essai(lambda: float(df["note_client"].dropna().le(2).mean() * 100)),
        "part_ca_telephonie_pct": essai(lambda: part_du_ca(livrees["categorie"] == "Téléphonie")),
        "meilleur_jour": essai(meilleur_jour),
    }


# clé : (libellé, unité, format, sens) ; sens True = plus haut, mieux ; False = plus bas, mieux ; None = neutre
LIBELLES = {
    "lignes":                 ("Lignes", "", "entier", None),
    "commandes_livrees":      ("Commandes livrées", "", "entier", True),
    "ca_fcfa":                ("Chiffre d'affaires", "M FCFA", "millions", True),
    "panier_moyen_fcfa":      ("Panier moyen", "FCFA", "entier", True),
    "prix_moyen_fcfa":        ("Prix unitaire moyen", "FCFA", "entier", None),
    "clients_actifs":         ("Clients actifs", "", "entier", True),
    "clients_par_telephone":  ("Clients comptés par téléphone", "", "entier", True),
    "taux_reachat_pct":       ("Taux de réachat", "%", "1", True),
    "retention_s1_pct":       ("Rétention de la semaine 1", "%", "1", True),
    "note_moyenne":           ("Note moyenne", "/\u202f5", "2", True),
    "part_insatisfaits_pct":  ("Clients insatisfaits", "%", "1", False),
    "delai_moyen_j":          ("Délai moyen de livraison", "j", "2", False),
    "part_mobile_money_pct":  ("Part Mobile Money", "%", "2", None),
    "part_ca_cotonou_pct":    ("Part du CA à Cotonou", "%", "2", None),
    "part_ca_telephonie_pct": ("Part du CA en Téléphonie", "%", "1", None),
    "taux_annulation_pct":    ("Taux d'annulation", "%", "1", False),
    "meilleur_jour":          ("Meilleur jour", "", "date", None),
}

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def est_manquant(x):
    """Vrai pour None, NaN, NaT et <NA>."""
    try:
        return bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def nombre(x, decimales=0):
    """Nombre au format français : 1 918,8 (espace fine, virgule décimale)."""
    if est_manquant(x):
        return "incalculable"
    x = float(x)
    if round(x, decimales) == 0:                             # pas de « −0,0 »
        x = 0.0
    texte = f"{x:,.{decimales}f}"
    texte = texte.replace(",", "§").replace(".", ",").replace("§", ESPACE_FINE)
    return texte.replace("-", "−")


def fcfa(x, decimales=None):
    """Montant en FCFA au format français : « 1 918,8 M FCFA » au-delà du million, sinon « 26 280 FCFA »."""
    if est_manquant(x):
        return "incalculable"
    if abs(round(float(x))) >= 1e6:
        return f"{nombre(float(x) / 1e6, 1 if decimales is None else decimales)}{ESPACE_FINE}M{ESPACE_FINE}FCFA"
    return f"{nombre(x, 0 if decimales is None else decimales)}{ESPACE_FINE}FCFA"


def jour_fr(texte):
    """« 2026-09-22 » → « 22 sept. 2026 » ; « 2026-09-01 » → « 1er sept. 2026 »."""
    if est_manquant(texte):
        return "incalculable"
    d = pd.Timestamp(str(texte))
    if pd.isna(d):
        return "incalculable"
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {MOIS[d.month - 1]} {d.year}"


def formater(cle, valeur):
    """Valeur d'un indicateur, formatée selon LIBELLES."""
    _, unite, fmt, _ = LIBELLES[cle]
    if est_manquant(valeur):
        return "incalculable"
    if fmt == "date":
        return jour_fr(valeur)
    if fmt == "millions":
        return fcfa(valeur)
    if fmt == "entier":
        texte = nombre(valeur, 0)
    else:
        texte = nombre(valeur, int(fmt))
    return f"{texte}{ESPACE_FINE}{unite}" if unite else texte


def ecart_pct(valeur, reference):
    """Écart relatif en % ; NaN si l'une des deux valeurs manque ou si la référence est nulle."""
    try:
        v, r = float(valeur), float(reference)
    except (TypeError, ValueError):
        return np.nan
    if math.isnan(v) or math.isnan(r) or r == 0:
        return np.nan
    return (v - r) / abs(r) * 100


def formater_ecart(e, decimales=1):
    """« +41,8 % », « −45,8 % », « = » ; vide si incalculable."""
    if est_manquant(e):
        return ""
    if round(float(e), decimales) == 0:
        return "="
    signe = "+" if e > 0 else ""
    return f"{signe}{nombre(e, decimales)}{ESPACE_FINE}%"


def tableau_kpis(kpis):
    """Liste de dictionnaires (ou dict nom → dict) d'indicateurs → DataFrame scénarios × indicateurs."""
    if isinstance(kpis, dict):
        return pd.DataFrame.from_dict(kpis, orient="index")
    return pd.DataFrame(kpis)


def comparer(kpis_df, reference="1_recommande"):
    """Écarts en % de chaque scénario (lignes) par rapport au scénario de référence, indicateur par indicateur."""
    numeriques = [c for c in kpis_df.columns if c in LIBELLES and LIBELLES[c][2] != "date"]
    ref = kpis_df.loc[reference]
    ecarts = pd.DataFrame(index=kpis_df.index, columns=numeriques, dtype=float)
    for scen in kpis_df.index:
        for col in numeriques:
            ecarts.loc[scen, col] = ecart_pct(kpis_df.loc[scen, col], ref[col])
    return ecarts


def tableau_lisible(kpis_df, cles):
    """Indicateurs au format français, une colonne par indicateur (libellé), une ligne par scénario."""
    lisible = pd.DataFrame(index=kpis_df.index)
    for cle in cles:
        lisible[LIBELLES[cle][0]] = [formater(cle, v) for v in kpis_df[cle]]
    return lisible
