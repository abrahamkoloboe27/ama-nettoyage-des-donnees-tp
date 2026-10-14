"""Tableau de bord du TP « Nettoyage des données » (module 13, AMA) : comparer les décisions de nettoyage.

Lancement, depuis la racine du dépôt :

    uv run streamlit run dashboard/app.py

Le tableau de bord lit ce que produisent les parties 6 et 7 du notebook :
- output/scenarios/tous_les_scenarios.parquet (partie 7 ; à défaut, chaque output/scenarios/<scénario>.parquet) ;
- output/progression_kpis.csv et output/journal_nettoyage.csv (partie 6), s'ils existent ;
- data/oracle/note_vraie.csv (les vraies notes), s'il existe.
Les indicateurs sont recalculés avec les fonctions du notebook (tp_nettoyage.kpis et tp_nettoyage.qualite).
"""
import io
import os
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from tp_nettoyage import config
from tp_nettoyage.config import COULEURS, TZ
from tp_nettoyage.kpis import (
    ESPACE_FINE,
    LIBELLES,
    calculer_kpis,
    comparer,
    est_manquant,
    fcfa,
    formater,
    formater_ecart,
    jour_fr,
    nombre,
    tableau_kpis,
)
from tp_nettoyage.scenarios import FICHIER_CONSOLIDE, LIBELLES_SCENARIOS, charger_scenarios
from tp_nettoyage.qualite import NOM_VOLUMETRIE, NOMS_TESTS, tests_qualite

VERT, ROUGE, GRIS = COULEURS["qualite"], COULEURS["aberrantes"], COULEURS["gris"]
MARINE, BLEU = COULEURS["marine"], COULEURS["types"]

# Les six cartes de la vue d'ensemble, et les indicateurs affichés par défaut dans le tableau.
CARTES = ["ca_fcfa", "prix_moyen_fcfa", "clients_par_telephone", "taux_reachat_pct", "note_moyenne", "part_insatisfaits_pct"]
INDICATEURS_DEFAUT = ["ca_fcfa", "prix_moyen_fcfa", "clients_par_telephone", "taux_reachat_pct", "note_moyenne",
                      "part_insatisfaits_pct", "part_ca_telephonie_pct", "delai_moyen_j", "meilleur_jour"]
NUMERIQUES = [cle for cle in LIBELLES if LIBELLES[cle][2] != "date"]

# Onglet « Raconter » : indicateurs parmi lesquels on cherche les trois plus gros écarts
# (lignes, commandes livrées, clients actifs et panier moyen sont laissés de côté : ils redisent la même chose).
A_RACONTER = ["ca_fcfa", "prix_moyen_fcfa", "clients_par_telephone", "taux_reachat_pct", "retention_s1_pct", "note_moyenne",
              "part_insatisfaits_pct", "delai_moyen_j", "part_mobile_money_pct", "part_ca_cotonou_pct",
              "part_ca_telephonie_pct", "taux_annulation_pct"]
DANS_UNE_PHRASE = {
    "ca_fcfa": "le chiffre d'affaires",
    "prix_moyen_fcfa": "le prix unitaire moyen",
    "clients_par_telephone": "le nombre de clients comptés par téléphone",
    "taux_reachat_pct": "le taux de réachat",
    "retention_s1_pct": "la rétention de la semaine 1",
    "note_moyenne": "la note moyenne",
    "part_insatisfaits_pct": "la part de clients insatisfaits",
    "delai_moyen_j": "le délai moyen de livraison",
    "part_mobile_money_pct": "la part Mobile Money",
    "part_ca_cotonou_pct": "la part du CA à Cotonou",
    "part_ca_telephonie_pct": "la part du CA en Téléphonie",
    "taux_annulation_pct": "le taux d'annulation",
}
EN_LETTRES = ["Aucun", "Un", "Deux", "Trois", "Quatre", "Cinq", "Six", "Sept", "Huit", "Neuf", "Dix"]
MOIS_LONGS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
              "décembre"]

# Couleur de chaque étape de la cascade (même code couleur que le cours).
COULEURS_ETAPES = {"0": MARINE, "1": COULEURS["types"], "2": COULEURS["types"], "3": COULEURS["doublons"],
                   "4": COULEURS["aberrantes"], "5": COULEURS["manquants"]}

# Colonnes indispensables pour qu'un scénario (fichier du dossier ou Parquet déposé) soit comparable aux autres.
COLONNES_UTILES = ["commande_id", "date_commande", "client_id", "telephone", "ville", "categorie", "quantite",
                   "prix_unitaire_fcfa", "montant_fcfa", "moyen_paiement", "statut", "note_client", "date_livraison"]

# Les deux colonnes de contrôle restent visibles quand on fait défiler un tableau large.
CONTROLES_EPINGLES = {"Tests qualité": st.column_config.Column(pinned=True), "Volumétrie": st.column_config.Column(pinned=True)}

# Nombres au format français dans les axes des graphiques Altair.
LOCALE_FR = {"number": {"decimal": ",", "thousands": ESPACE_FINE, "grouping": [3], "currency": ["", f"{ESPACE_FINE}FCFA"]}}


# ---------------------------------------------------------------- lecture des données
def dossiers():
    """Dossiers du TP, calculés à chaque exécution : TP_NETTOYAGE_RACINE si elle existe, sinon la racine trouvée par config."""
    racine = Path(os.environ["TP_NETTOYAGE_RACINE"]) if os.environ.get("TP_NETTOYAGE_RACINE") else config.RACINE
    return racine / "output" / "scenarios", racine / "output", racine / "data" / "oracle" / "note_vraie.csv"


def dates_de_modification(dossier):
    """(nom, date de modification) de chaque Parquet du dossier : la clé du cache change dès qu'un fichier change."""
    return tuple((p.name, p.stat().st_mtime) for p in sorted(dossier.glob("*.parquet")))


def en_dates(s):
    """Colonne de dates avec fuseau ; une date sans fuseau est lue à l'heure de la boutique (Africa/Porto-Novo)."""
    if not pd.api.types.is_datetime64_any_dtype(s):
        s = pd.to_datetime(s, format="ISO8601")
    if s.dt.tz is None:
        s = s.dt.tz_localize(TZ)
    return s


def preparer(df):
    """Vérifie les colonnes et met des dates avec fuseau : (DataFrame, None), ou (None, message d'erreur)."""
    manquantes = [c for c in COLONNES_UTILES if c not in df.columns]
    if manquantes:
        return None, "Colonnes manquantes : " + ", ".join(manquantes) + "."
    df = df.copy()
    try:
        for col in ["date_commande", "date_livraison"]:
            df[col] = en_dates(df[col])
        if "double_clic" in df.columns:
            df["double_clic"] = df["double_clic"].astype("boolean")
    except (TypeError, ValueError) as e:
        return None, f"Les dates ou le drapeau double_clic n'ont pas le bon type ({type(e).__name__})."
    return df, None


@st.cache_data(show_spinner="Lecture des scénarios…")
def lire_scenarios(dossier, mtime):
    """Les scénarios du dossier (dict nom → DataFrame) et les fichiers écartés (dict nom → raison).

    mtime (les dates de modification des fichiers) ne sert qu'à renouveler le cache quand un fichier change.
    """
    frames, ecartes = {}, {}
    for nom, lu in charger_scenarios(dossier).items():
        df, erreur = preparer(lu)
        if erreur:
            ecartes[nom] = erreur
        else:
            frames[nom] = df
    return frames, ecartes


def indicateurs(df):
    """Indicateurs métier et tests qualité d'un scénario (comme kpis_et_tests, avec en plus le nom des tests en échec)."""
    tests = tests_qualite(df)
    huit = tests[NOMS_TESTS]
    return {**calculer_kpis(df),
            "tests_qualite": int(huit.sum()),
            "volumetrie": bool(tests[NOM_VOLUMETRIE]),
            "tests_en_echec": " · ".join(huit.index[~huit.to_numpy(dtype=bool)])}


@st.cache_data(show_spinner="Calcul des indicateurs…")
def calculer_indicateurs(dossier, mtime):
    """Tableau scénarios × indicateurs (une ligne par scénario)."""
    frames, _ = lire_scenarios(dossier, mtime)
    return tableau_kpis({nom: indicateurs(d) for nom, d in frames.items()})


@st.cache_data
def lire_csv(chemin, mtime, texte_brut):
    """texte_brut=True : « NaN » ou « NaT » restent du texte (les décisions du journal)."""
    return pd.read_csv(chemin, keep_default_na=not texte_brut)


def lire_rapport(chemin, texte_brut=False):
    """Le CSV s'il existe et se lit, sinon None."""
    if not chemin.exists():
        return None
    try:
        return lire_csv(str(chemin), chemin.stat().st_mtime, texte_brut)
    except (OSError, ValueError):
        return None


@st.cache_data(show_spinner="Lecture du fichier déposé…")
def lire_depot(contenu):
    """Parquet déposé → (DataFrame, None) s'il est utilisable, sinon (None, message d'erreur)."""
    try:
        df = pd.read_parquet(io.BytesIO(contenu))
    except Exception as e:  # fichier abîmé, autre format : on explique au lieu de planter
        return None, f"Ce fichier n'est pas un Parquet lisible ({type(e).__name__})."
    if df.empty:
        return None, "Ce fichier ne contient aucune ligne."
    if "scenario" in df.columns:
        if df["scenario"].nunique() > 1:
            return None, "Ce fichier réunit plusieurs scénarios (colonne « scenario ») : déposez le Parquet d'un seul scénario."
        if "fuseau" in df.columns:                    # fichier passé par harmoniser : dates en UTC, fuseau d'origine noté
            try:
                for col in ["date_commande", "date_livraison", "maj_le"]:
                    if col in df.columns and isinstance(df[col].dtype, pd.DatetimeTZDtype):
                        df[col] = df[col].dt.tz_convert(str(df["fuseau"].iloc[0]))
            except Exception as e:  # fuseau inconnu : on explique au lieu de planter
                return None, f"Fuseau illisible dans la colonne « fuseau » ({type(e).__name__})."
        df = df.drop(columns=["scenario", "fuseau"], errors="ignore")
    return preparer(df)


def lire_oracle(chemin):
    """Les vraies notes (commande_id, note_vraie), ou None si le fichier manque."""
    oracle = lire_rapport(chemin)
    if oracle is None or not {"commande_id", "note_vraie"} <= set(oracle.columns):
        return None
    return oracle


# ---------------------------------------------------------------- petits calculs
def libelle(code):
    """Nom lisible d'un scénario."""
    if code == "mon_scenario":
        return "Mon scénario (fichier déposé)"
    return LIBELLES_SCENARIOS.get(code, code)


def nom_scenario(code):
    """« Doublons gardés (2_doublons_gardes) » ; le code seul pour un scénario inconnu."""
    return f"{libelle(code)} ({code})" if libelle(code) != code else code


def titre_axe(cle):
    nom, unite, _, _ = LIBELLES[cle]
    return f"{nom} ({unite})" if unite else nom


def livrees(df):
    """Commandes livrées, hors doubles clics (la même règle que calculer_kpis)."""
    resultat = df[df["statut"] == "livrée"]
    if "double_clic" in resultat.columns:
        resultat = resultat[~resultat["double_clic"].astype("boolean").fillna(False)]
    return resultat


def ca_par_jour(df):
    """CA des commandes livrées par jour ; le jour est lu dans le fuseau du scénario (index « AAAA-MM-JJ »)."""
    commandes = livrees(df)
    ca = commandes.groupby(commandes["date_commande"].dt.date)["montant_fcfa"].sum()
    ca.index = ca.index.astype("str")
    return ca


def ca_par(df, colonne):
    """CA des commandes livrées par ville ou par catégorie (les cases vides deviennent « (vide) »)."""
    commandes = livrees(df)
    return commandes.groupby(commandes[colonne].astype("str").fillna("(vide)"))["montant_fcfa"].sum()


def dire(cle, valeur, decimales=1):
    """Valeur pour une phrase : comme formater, avec une seule décimale (par défaut) pour les pourcentages et les jours."""
    unite = LIBELLES[cle][1]
    if est_manquant(valeur) or unite not in ("%", "j"):
        return formater(cle, valeur)
    return f"{nombre(valeur, decimales)}{ESPACE_FINE}{'%' if unite == '%' else 'jours'}"


def jour_long(texte):
    """« 2026-09-01 » → « 1er septembre »."""
    d = pd.Timestamp(str(texte))
    return f"{'1er' if d.day == 1 else d.day} {MOIS_LONGS[d.month - 1]}"


def enumerer(morceaux):
    """« a, b et c »."""
    return morceaux[0] if len(morceaux) == 1 else ", ".join(morceaux[:-1]) + " et " + morceaux[-1]


def entre_parentheses(ecart):
    """« (+41,8 %) », ou rien si l'écart est incalculable."""
    texte = formater_ecart(ecart)
    return f" ({texte})" if texte else ""


def coche(valeur):
    return "✅" if str(valeur) == "True" else "❌"


# ---------------------------------------------------------------- vue d'ensemble
def style_ecart(cle, ecart):
    """Vert si l'écart va dans le bon sens, rouge sinon, gris pour un indicateur neutre ; rien si pas d'écart."""
    if est_manquant(ecart) or round(float(ecart), 1) == 0:
        return ""
    sens = LIBELLES[cle][3]
    if sens is None:
        return f"color: {GRIS}"
    bon = (ecart > 0) == sens
    return f"color: {VERT if bon else ROUGE}; font-weight: 600"


def tableau_comparatif(kpis, ecarts, lignes, cles, reference):
    """Scénarios × indicateurs : valeur au format français, écart à la référence entre parenthèses, couleurs."""
    textes, styles = [], []
    for code in lignes:
        texte, style = {}, {}
        for cle in cles:
            nom, valeur = LIBELLES[cle][0], kpis.loc[code, cle]
            if cle == "meilleur_jour":
                change = code != reference and str(valeur) != str(kpis.loc[reference, cle])
                texte[nom] = formater(cle, valeur) + (" (changé)" if change else "")
                style[nom] = f"color: {GRIS}; font-weight: 600" if change else ""
            elif code == reference:
                texte[nom], style[nom] = formater(cle, valeur), ""
            elif LIBELLES[cle][1] == "j":                # un délai : l'écart en jours, car le signe peut s'inverser
                ecart_j = ecart_dans_phrase(cle, valeur, kpis.loc[reference, cle], ecarts.loc[code, cle])
                texte[nom] = formater(cle, valeur) + (f" ({ecart_j})" if ecart_j else "")
                style[nom] = style_ecart(cle, ecarts.loc[code, cle])
            else:
                texte[nom] = formater(cle, valeur) + entre_parentheses(ecarts.loc[code, cle])
                style[nom] = style_ecart(cle, ecarts.loc[code, cle])
        reussis = int(kpis.loc[code, "tests_qualite"])
        texte["Tests qualité"] = f"{reussis} / 8"
        style["Tests qualité"] = f"color: {VERT if reussis == 8 else ROUGE}; font-weight: 600"
        texte["Volumétrie"], style["Volumétrie"] = coche(kpis.loc[code, "volumetrie"]), ""
        texte["Tests en échec"], style["Tests en échec"] = kpis.loc[code, "tests_en_echec"] or "aucun", ""
        if code == reference:                         # la ligne de référence sur fond bleu clair
            fond = f"background-color: {COULEURS['bleu_clair']}"
            style = {nom: f"{s}; {fond}" if s else fond for nom, s in style.items()}
        textes.append(texte)
        styles.append(style)
    index = [nom_scenario(code) for code in lignes]
    styles = pd.DataFrame(styles, index=index)
    return pd.DataFrame(textes, index=index).style.apply(lambda _: styles, axis=None)


def onglet_vue_ensemble(kpis, ecarts, lignes, cles, reference):
    st.subheader(f"Référence : {nom_scenario(reference)}")
    for rangee in (CARTES[:3], CARTES[3:]):
        for colonne, cle in zip(st.columns(3), rangee):
            colonne.metric(LIBELLES[cle][0], formater(cle, kpis.loc[reference, cle]), border=True)
    st.subheader("Tous les scénarios comparés")
    if not cles:
        st.info("Choisissez des indicateurs dans la barre latérale : seuls les contrôles sont affichés.")
    st.dataframe(tableau_comparatif(kpis, ecarts, lignes, cles, reference), width="stretch", column_config=CONTROLES_EPINGLES)
    st.caption("Entre parenthèses : l'écart à la référence (en jours pour le délai de livraison). "
               "Vert : l'écart va dans le bon sens pour l'indicateur ; rouge : dans le mauvais sens ; "
               "gris : indicateur neutre (ni bon ni mauvais en soi). « = » : écart inférieur à 0,05 % (arrondi à 0,0 %). "
               "Attention : vert ne veut pas dire juste, un écart « favorable » peut venir d'une erreur de nettoyage. "
               "Les contrôles : les 8 tests qualité du cours et la volumétrie (≥ 95 % des commandes).")


# ---------------------------------------------------------------- cascade du nettoyage
def axe_etapes(etapes):
    return alt.X("etape:N", sort=etapes, title=None, axis=alt.Axis(labelAngle=-35, labelLimit=220, labelOverlap=False))


def courbe_etapes(prog, cle):
    """Valeur de l'indicateur à chaque étape : une courbe, un point par étape aux couleurs du cours."""
    etapes = list(prog.index)
    valeurs = pd.to_numeric(prog[cle], errors="coerce")
    donnees = pd.DataFrame({"etape": etapes,
                            "valeur": (valeurs / 1e6 if cle == "ca_fcfa" else valeurs).to_numpy(),
                            "texte": [formater(cle, v) for v in prog[cle]]})
    couleurs = [COULEURS_ETAPES.get(str(e)[:1], BLEU) for e in etapes]
    base = alt.Chart(donnees).encode(x=axe_etapes(etapes),
                                     y=alt.Y("valeur:Q", title=titre_axe(cle), scale=alt.Scale(zero=False)),
                                     tooltip=[alt.Tooltip("etape:N", title="Étape"), alt.Tooltip("texte:N", title=LIBELLES[cle][0])])
    ligne = base.mark_line(color=MARINE)
    points = base.mark_circle(size=140, opacity=1).encode(
        color=alt.Color("etape:N", scale=alt.Scale(domain=etapes, range=couleurs), legend=None))
    return (ligne + points).properties(height=320, title=LIBELLES[cle][0]).configure(locale=LOCALE_FR)


def barres_tests(prog):
    """Nombre de tests qualité réussis (sur 8) à chaque étape."""
    etapes = list(prog.index)
    reussis = pd.to_numeric(prog["tests_qualite"], errors="coerce").fillna(0).astype(int)
    donnees = pd.DataFrame({"etape": etapes, "tests": reussis.to_numpy(),
                            "etiquette": [f"{n} / 8" for n in reussis],
                            "etat": ["8 / 8" if n == 8 else "incomplet" for n in reussis]})
    base = alt.Chart(donnees).encode(x=axe_etapes(etapes),
                                     y=alt.Y("tests:Q", title="Tests qualité réussis (sur 8)", scale=alt.Scale(domain=[0, 8])))
    barres = base.mark_bar().encode(
        color=alt.Color("etat:N", scale=alt.Scale(domain=["8 / 8", "incomplet"], range=[VERT, COULEURS["manquants"]]), legend=None),
        tooltip=[alt.Tooltip("etape:N", title="Étape"), alt.Tooltip("etiquette:N", title="Tests qualité")])
    etiquettes = base.mark_text(dy=-8, color=COULEURS["texte"]).encode(text="etiquette:N")
    return (barres + etiquettes).properties(height=320, title="Tests qualité").configure(locale=LOCALE_FR)


def tableau_etapes(prog, cles):
    """Une ligne par étape : indicateurs au format français et contrôles."""
    lignes = []
    for _, ligne in prog.iterrows():
        texte = {LIBELLES[cle][0]: formater(cle, ligne[cle]) for cle in cles if cle in prog.columns}
        if "tests_qualite" in prog.columns:
            texte["Tests qualité"] = f"{nombre(ligne['tests_qualite'])} / 8"
        if "volumetrie" in prog.columns:
            texte["Volumétrie"] = coche(ligne["volumetrie"])
        if "tests_en_echec" in prog.columns:
            texte["Tests en échec"] = ligne["tests_en_echec"] if isinstance(ligne["tests_en_echec"], str) else "aucun"
        lignes.append(texte)
    return pd.DataFrame(lignes, index=pd.Index(prog.index, name="étape"))


def onglet_cascade(progression, cles):
    st.subheader("Cascade du nettoyage du scénario recommandé")
    if progression is None or "étape" not in progression.columns:
        st.info("Fichier output/progression_kpis.csv introuvable : lancez d'abord la partie 6 du notebook, "
                "qui l'écrit avec suivi.exporter.")
        return
    prog = progression.set_index("étape")
    possibles = [cle for cle in NUMERIQUES if cle in prog.columns]
    if not possibles:
        st.warning("output/progression_kpis.csv ne contient aucun indicateur connu.")
        return
    cle = st.selectbox("Indicateur suivi", possibles, index=possibles.index("ca_fcfa") if "ca_fcfa" in possibles else 0,
                       format_func=lambda c: LIBELLES[c][0], key="cascade_indicateur")
    gauche, droite = st.columns(2)
    with gauche:
        st.altair_chart(courbe_etapes(prog, cle), width="stretch")
        incalculables = [str(e) for e, v in prog[cle].items() if est_manquant(v)]
        if incalculables:
            st.caption("Incalculable (pas de point) à l'étape : " + ", ".join(f"« {e} »" for e in incalculables) + ".")
    with droite:
        if "tests_qualite" in prog.columns:
            st.altair_chart(barres_tests(prog), width="stretch")
            reussis = pd.to_numeric(prog["tests_qualite"], errors="coerce")
            st.caption(f"Les tests qualité passent de {nombre(reussis.iloc[0])} / 8 (étape « {prog.index[0]} ») "
                       f"à {nombre(reussis.iloc[-1])} / 8 (étape « {prog.index[-1]} »).")
    st.dataframe(tableau_etapes(prog, cles), width="stretch", column_config=CONTROLES_EPINGLES)


# ---------------------------------------------------------------- zoom
def barres_scenarios(kpis, lignes, reference, cle):
    """Une barre par scénario, la référence en bleu marine et une règle verticale à sa valeur."""
    echelle = 1e6 if LIBELLES[cle][2] == "millions" else 1
    valeurs = pd.to_numeric(kpis.loc[lignes, cle], errors="coerce") / echelle
    donnees = pd.DataFrame({"scenario": [nom_scenario(c) for c in lignes], "valeur": valeurs.to_numpy(),
                            "texte": [formater(cle, kpis.loc[c, cle]) for c in lignes],
                            "role": ["référence" if c == reference else "scénario" for c in lignes]})
    base = alt.Chart(donnees).encode(y=alt.Y("scenario:N", sort=None, title=None, axis=alt.Axis(labelLimit=320)),
                                     x=alt.X("valeur:Q", title=titre_axe(cle)))
    barres = base.mark_bar().encode(
        color=alt.Color("role:N", scale=alt.Scale(domain=["référence", "scénario"], range=[MARINE, BLEU]), legend=None),
        tooltip=[alt.Tooltip("scenario:N", title="Scénario"), alt.Tooltip("texte:N", title=LIBELLES[cle][0])])
    graphique = barres + base.mark_text(align="left", dx=4, color=COULEURS["texte"]).encode(text="texte:N")
    valeur_ref = valeurs[reference]
    if not est_manquant(valeur_ref):
        regle = pd.DataFrame({"valeur": [valeur_ref]})
        graphique = graphique + alt.Chart(regle).mark_rule(color=MARINE, strokeDash=[6, 4], size=2).encode(x="valeur:Q")
    return graphique.properties(height=max(120, 42 * len(lignes)), padding={"right": 90}).configure(locale=LOCALE_FR)


def couleur_duo(noms):
    return alt.Color("scenario:N", scale=alt.Scale(domain=noms, range=[MARINE, BLEU][:len(noms)]),
                     legend=alt.Legend(title=None, orient="bottom", direction="vertical", labelLimit=400))


def barres_groupees(frames, duo, colonne):
    """CA par ville ou par catégorie : la référence et le scénario choisi côte à côte."""
    morceaux = []
    for code in duo:
        ca = ca_par(frames[code], colonne)
        morceaux.append(pd.DataFrame({"modalite": ca.index, "ca": ca.to_numpy() / 1e6, "scenario": nom_scenario(code),
                                      "texte": [fcfa(v) for v in ca]}))
    donnees = pd.concat(morceaux, ignore_index=True)
    noms = [nom_scenario(code) for code in duo]
    graphique = alt.Chart(donnees).mark_bar().encode(
        y=alt.Y("modalite:N", sort="-x", title=None),
        x=alt.X("ca:Q", title="CA des commandes livrées (M FCFA)"),
        yOffset=alt.YOffset("scenario:N", sort=noms),
        color=couleur_duo(noms),
        tooltip=[alt.Tooltip("modalite:N", title="Ville" if colonne == "ville" else "Catégorie"), alt.Tooltip("scenario:N", title="Scénario"),
                 alt.Tooltip("texte:N", title="CA")])
    return graphique.configure(locale=LOCALE_FR)


def histogramme_prix(frames, duo):
    """Histogramme des prix unitaires : prix en échelle logarithmique (10 classes par puissance de 10), lignes en échelle symlog.

    L'échelle symlog garde visibles les classes de quelques lignes (les prix ×100) à côté de celles de plusieurs milliers.
    """
    prix = {}
    for code in duo:
        p = pd.to_numeric(frames[code]["prix_unitaire_fcfa"], errors="coerce").astype(float)
        prix[code] = p[p > 0]
    tous = pd.concat(list(prix.values()))
    if tous.empty:
        return None
    bas, haut = int(np.floor(np.log10(tous.min()))), int(np.ceil(np.log10(tous.max())))
    haut = max(haut, bas + 1)
    bords = np.logspace(bas, haut, (haut - bas) * 10 + 1)
    bords = bords[: np.searchsorted(bords, tous.max(), side="right") + 1]   # pas de classes vides au-delà du prix maximal
    morceaux = []
    for code, p in prix.items():
        effectifs, _ = np.histogram(p, bins=bords)
        morceaux.append(pd.DataFrame({"debut": bords[:-1], "fin": bords[1:], "lignes": effectifs, "scenario": nom_scenario(code),
                                      "classe": [f"{nombre(a)} à {nombre(b)} FCFA" for a, b in zip(bords[:-1], bords[1:])]}))
    donnees = pd.concat(morceaux, ignore_index=True)
    graduations = [m * 10 ** k for k in range(bas, haut + 1) for m in (1, 3) if m * 10 ** k <= bords[-1]]
    graphique = alt.Chart(donnees).mark_bar(opacity=0.6).encode(
        x=alt.X("debut:Q", scale=alt.Scale(type="log"), title="Prix unitaire (FCFA, échelle logarithmique)",
                axis=alt.Axis(values=graduations, format=",.0f", labelAngle=-30)),
        x2="fin:Q",
        y=alt.Y("lignes:Q", stack=None, scale=alt.Scale(type="symlog"), title="Nombre de lignes (échelle symlog)"),
        y2=alt.datum(0),
        color=couleur_duo([nom_scenario(code) for code in duo]),
        tooltip=[alt.Tooltip("scenario:N", title="Scénario"), alt.Tooltip("classe:N", title="Prix"),
                 alt.Tooltip("lignes:Q", title="Lignes", format=",.0f")])
    return graphique.properties(height=300).configure(locale=LOCALE_FR)


def courbe_jours(frames, duo):
    """CA des livrées par jour pour la référence et un autre scénario ; un losange marque le meilleur jour de chacun."""
    morceaux = []
    for code in duo:
        ca = ca_par_jour(frames[code])
        morceaux.append(pd.DataFrame({"jour": ca.index, "ca": ca.to_numpy() / 1e6, "scenario": nom_scenario(code),
                                      "texte": [f"{jour_fr(j)} · {fcfa(v)}" for j, v in ca.items()]}))
    donnees = pd.concat(morceaux, ignore_index=True)
    if donnees.empty:
        return None
    jours = sorted(donnees["jour"].unique())
    x = alt.X("jour:O", sort=jours, title=None,
              axis=alt.Axis(labelExpr="substring(datum.value, 8, 10) + '/' + substring(datum.value, 5, 7)", labelAngle=-45))
    couleur = couleur_duo([nom_scenario(code) for code in duo])
    infobulle = [alt.Tooltip("scenario:N", title="Scénario"), alt.Tooltip("texte:N", title="Jour et CA")]
    base = alt.Chart(donnees).encode(x=x, y=alt.Y("ca:Q", title="CA des commandes livrées (M FCFA)", scale=alt.Scale(zero=False)),
                                     color=couleur, tooltip=infobulle)
    records = donnees.loc[donnees.groupby("scenario")["ca"].idxmax()]
    losanges = alt.Chart(records).mark_point(shape="diamond", size=320, filled=True, opacity=1).encode(
        x=x, y="ca:Q", color=couleur, tooltip=infobulle)
    return (base.mark_line(point=True) + losanges).properties(height=340).configure(locale=LOCALE_FR)


def onglet_zoom(frames, kpis, lignes, reference, cles):
    st.subheader("Un indicateur, scénario par scénario")
    defaut = next((cle for cle in cles if cle in NUMERIQUES), "ca_fcfa")
    cle = st.selectbox("Indicateur", NUMERIQUES, index=NUMERIQUES.index(defaut), format_func=lambda c: LIBELLES[c][0],
                       key="zoom_indicateur")
    st.altair_chart(barres_scenarios(kpis, lignes, reference, cle), width="stretch")
    st.caption(f"Pointillés : la valeur de la référence ({formater(cle, kpis.loc[reference, cle])}).")

    st.subheader("La référence face à un autre scénario")
    autres = [code for code in lignes if code != reference]
    if autres:
        autre = st.selectbox("Scénario comparé", autres, format_func=nom_scenario, key="zoom_scenario")
        duo = [reference, autre]
    else:
        if len(frames) == 1:
            st.caption("Un seul scénario affiché : la référence est montrée seule. Lancez la partie 7 du notebook "
                       "pour produire les autres scénarios.")
        else:
            st.caption("Un seul scénario affiché : la référence est montrée seule (cochez d'autres scénarios dans la barre latérale).")
        duo = [reference]
    gauche, droite = st.columns(2)
    with gauche:
        st.markdown("**CA par ville**")
        st.altair_chart(barres_groupees(frames, duo, "ville"), width="stretch")
    with droite:
        st.markdown("**CA par catégorie**")
        st.altair_chart(barres_groupees(frames, duo, "categorie"), width="stretch")

    st.markdown("**Distribution des prix unitaires (échelle logarithmique)**")
    histogramme = histogramme_prix(frames, duo)
    if histogramme is None:
        st.info("Aucun prix positif à afficher.")
    else:
        st.altair_chart(histogramme, width="stretch")
        etendues = []
        for code in duo:
            p = pd.to_numeric(frames[code]["prix_unitaire_fcfa"], errors="coerce")
            etendues.append(f"« {libelle(code)} » : de {fcfa(p.min())} à {fcfa(p.max())}")
        st.caption("Prix unitaires " + " ; ".join(etendues) + ".")

    st.markdown("**CA par jour (commandes livrées hors doubles clics, jour lu dans le fuseau du scénario)**")
    if "6_fuseau_utc" in lignes and reference != "6_fuseau_utc":
        duo_jours = [reference, "6_fuseau_utc"]
    else:
        duo_jours = duo
    courbe = courbe_jours(frames, duo_jours)
    if courbe is None:
        st.info("Aucune commande livrée : pas de CA par jour.")
        return
    st.altair_chart(courbe, width="stretch")
    records = []
    for code in duo_jours:
        ca = ca_par_jour(frames[code])
        if not ca.empty:
            records.append(f"« {libelle(code)} » : {jour_fr(ca.idxmax())} ({fcfa(ca.max())})")
    st.caption("Meilleur jour (losange) " + " ; ".join(records) + ".")


# ---------------------------------------------------------------- raconter
def plus_gros_ecarts(code, ecarts, n=3):
    """Les n indicateurs de A_RACONTER qui s'écartent le plus de la référence (écart relatif absolu).

    Les écarts de moins de 1 % sont du bruit : on ne les cite que s'il n'y a rien de plus gros (et alors un seul).
    """
    e = pd.to_numeric(ecarts.loc[code, [c for c in A_RACONTER if c in ecarts.columns]], errors="coerce").dropna()
    e = e[e.round(1) != 0].abs().sort_values(ascending=False, kind="stable")
    gros = e[e >= 1]
    return list(gros.index[:n]) if not gros.empty else list(e.index[:1])


def ecart_dans_phrase(cle, valeur, valeur_ref, ecart):
    """Écart relatif (« −45,8 % ») ; pour un délai, écart en jours, car le signe peut s'inverser (−55,4 j contre 2,4 j)."""
    if LIBELLES[cle][1] == "j" and not est_manquant(valeur) and not est_manquant(valeur_ref):
        difference = float(valeur) - float(valeur_ref)
        decimales = 1 if round(difference, 1) != 0 else 2         # « +0,04 jours » plutôt que « +0,0 jours »
        if round(difference, decimales) == 0:
            return "="
        return f"{'+' if difference > 0 else ''}{nombre(difference, decimales)}{ESPACE_FINE}jours"
    return formater_ecart(ecart)


def a_la_reference(reference):
    return "au scénario recommandé" if reference == "1_recommande" else f"à « {libelle(reference)} »"


def phrase_ecarts(code, reference, kpis, ecarts, jours):
    """« Selon « … », <indicateur> vaut <valeur> au lieu de <référence> (<écart>) … ».

    Le meilleur jour vient en premier s'il change, puis les trois plus gros écarts.
    """
    morceaux = []
    jour, jour_ref = kpis.loc[code, "meilleur_jour"], kpis.loc[reference, "meilleur_jour"]
    if not est_manquant(jour) and not est_manquant(jour_ref) and str(jour) != str(jour_ref):
        morceaux.append(f"le meilleur jour devient le {jour_fr(jour)} ({fcfa(jours[code].get(str(jour)))}) "
                        f"au lieu du {jour_fr(jour_ref)} ({fcfa(jours[reference].get(str(jour_ref)))})")
    cles = plus_gros_ecarts(code, ecarts)
    if morceaux:                                      # le meilleur jour a changé : inutile d'ajouter un écart de moins de 1 %
        cles = [c for c in cles if abs(float(ecarts.loc[code, c])) >= 1]
    for i, cle in enumerate(cles):
        valeur, valeur_ref = dire(cle, kpis.loc[code, cle]), dire(cle, kpis.loc[reference, cle])
        if valeur == valeur_ref:                      # « 6,7 % au lieu de 6,7 % » : une décimale de plus
            valeur, valeur_ref = dire(cle, kpis.loc[code, cle], 2), dire(cle, kpis.loc[reference, cle], 2)
        precision = f" par rapport {a_la_reference(reference)}" if i == 0 else ""
        ecart = ecart_dans_phrase(cle, kpis.loc[code, cle], kpis.loc[reference, cle], ecarts.loc[code, cle])
        morceaux.append(f"{DANS_UNE_PHRASE[cle]} vaut {valeur} au lieu de {valeur_ref} ({ecart}{precision})")
    if not morceaux:
        return f"Selon « {libelle(code)} », aucun indicateur ne s'écarte de la référence (à 0,05 % près)."
    return f"Selon « {libelle(code)} », {enumerer(morceaux)}."


def phrase_tests(ligne):
    reussis, volumetrie = int(ligne["tests_qualite"]), bool(ligne["volumetrie"])
    if reussis == 8 and volumetrie:
        return "**Contrôles.** Les 8 tests qualité passent et la volumétrie est respectée."
    if reussis == 8:
        return "**Contrôles.** Les 8 tests qualité passent : seule la volumétrie refuse ce fichier."
    volume = "respectée" if volumetrie else "non respectée"
    return f"**Contrôles.** {reussis} / 8 tests qualité réussis (en échec : {ligne['tests_en_echec']}) ; volumétrie {volume}."


def verite(df, oracle):
    """Vraie note moyenne et vraie part de notes ≤ 2 (d'après l'oracle) sur les commandes livrées ou retournées de df."""
    commandes = df.loc[df["statut"].isin(["livrée", "retournée"]), ["commande_id"]].astype("str")
    notes = commandes.merge(oracle.astype({"commande_id": "str"}), on="commande_id", how="inner")["note_vraie"].dropna()
    return notes.mean(), notes.le(2).mean() * 100


def histoire(code, reference, kpis, ecarts, frames, jours, oracle):
    """(phrase trompeuse, explication) pour un scénario connu du cours ; (None, leçon) ou (None, None) sinon."""
    v, r, e = kpis.loc[code], kpis.loc[reference], ecarts.loc[code]

    if code == "0_brut_type" and not est_manquant(v["clients_par_telephone"]):
        phrase = f"Nous avons {nombre(round(v['clients_par_telephone'], -3))} clients"
        phrase += " et Cotonou recule." if v["part_ca_cotonou_pct"] < r["part_ca_cotonou_pct"] else "."
        return phrase, (
            f"Elle s'appuie sur {dire('clients_par_telephone', v['clients_par_telephone'])} clients comptés par téléphone "
            f"au lieu de {dire('clients_par_telephone', r['clients_par_telephone'])}{entre_parentheses(e['clients_par_telephone'])} : "
            "un même numéro écrit de plusieurs façons (avec « +229 », avec des espaces, sans le « 01 ») compte pour plusieurs clients. "
            f"Cotonou pèse {dire('part_ca_cotonou_pct', v['part_ca_cotonou_pct'])} du CA au lieu de "
            f"{dire('part_ca_cotonou_pct', r['part_ca_cotonou_pct'])} : « Ctn », « Cotonu » ou « COTONOU » ne comptent pas comme Cotonou. "
            f"De même, la part Mobile Money vaut {dire('part_mobile_money_pct', v['part_mobile_money_pct'])} au lieu de "
            f"{dire('part_mobile_money_pct', r['part_mobile_money_pct'])}, car « MoMo » ou « momo » ne sont pas reconnus.")

    if code == "2_doublons_gardes" and v["ca_fcfa"] > r["ca_fcfa"]:
        explication = (f"Ce chiffre compte deux fois {fcfa(v['ca_fcfa'] - r['ca_fcfa'])}{entre_parentheses(e['ca_fcfa'])} : "
                       "les lignes en double, les anciennes versions des commandes et les doubles clics sont restés dans le CA.")
        if "commande_id unique" in v["tests_en_echec"]:
            explication += " Le test « commande_id unique » échoue : il aurait dû vous alerter."
        return f"Septembre a rapporté {fcfa(v['ca_fcfa'])}.", explication

    if code == "3_aberrantes_iqr" and v["part_ca_telephonie_pct"] < r["part_ca_telephonie_pct"]:
        ref = frames[reference]
        supprimees = ref[~ref["commande_id"].isin(frames[code]["commande_id"])]
        explication = (
            f"Elle s'appuie sur une part du CA en Téléphonie de {dire('part_ca_telephonie_pct', v['part_ca_telephonie_pct'])} au lieu de "
            f"{dire('part_ca_telephonie_pct', r['part_ca_telephonie_pct'])}, un prix unitaire moyen de "
            f"{formater('prix_moyen_fcfa', v['prix_moyen_fcfa'])}{entre_parentheses(e['prix_moyen_fcfa'])} "
            f"et un CA de {fcfa(v['ca_fcfa'])}{entre_parentheses(e['ca_fcfa'])}.")
        if len(supprimees):
            part = (supprimees["categorie"].astype("str") == "Téléphonie").mean() * 100
            explication += (f" La règle de l'IQR sur le prix a supprimé {nombre(len(supprimees))} lignes, dont {nombre(part, 0)}{ESPACE_FINE}% "
                            "de téléphones : ces prix élevés ne sont pas des erreurs, la Téléphonie est la catégorie la plus chère.")
        return "La Téléphonie s'effondre.", explication

    if code == "4_manquants_dropna" and v["taux_annulation_pct"] == 0 and r["lignes"] > 0:
        part = v["lignes"] / r["lignes"] * 100
        return "Plus aucune commande annulée en septembre.", (
            f"Elle s'appuie sur un taux d'annulation de {dire('taux_annulation_pct', v['taux_annulation_pct'])} au lieu de "
            f"{dire('taux_annulation_pct', r['taux_annulation_pct'])}. Or dropna() n'a gardé que {nombre(v['lignes'])} lignes sur "
            f"{nombre(r['lignes'])} ({nombre(part, 1)}{ESPACE_FINE}%) : une commande annulée n'a pas de date de livraison, "
            "donc toutes les annulées sont parties avec les autres lignes incomplètes.")

    if code == "5_manquants_zero" and not est_manquant(v["part_insatisfaits_pct"]):
        sur_dix = int(round(v["part_insatisfaits_pct"] / 10))
        if sur_dix == 0:
            return None, None
        phrase = f"{EN_LETTRES[sur_dix]} clients sur dix sont mécontents." if sur_dix >= 2 else "Un client sur dix est mécontent."
        explication = (f"Elle s'appuie sur {dire('part_insatisfaits_pct', v['part_insatisfaits_pct'])} de notes inférieures ou égales à 2 "
                       f"au lieu de {dire('part_insatisfaits_pct', r['part_insatisfaits_pct'])}, et une note moyenne de "
                       f"{formater('note_moyenne', v['note_moyenne'])} au lieu de {formater('note_moyenne', r['note_moyenne'])} : "
                       "les notes vides, remplacées par 0, comptent comme des notes de 0 sur 5.")
        if "note entre 1 et 5" in v["tests_en_echec"]:
            explication += " Le test « note entre 1 et 5 » le signale."
        return phrase, explication

    jour, jour_ref = v["meilleur_jour"], r["meilleur_jour"]
    if code == "6_fuseau_utc" and not est_manquant(jour) and not est_manquant(jour_ref) and jour != jour_ref:
        return f"Le record du mois a eu lieu le {jour_long(jour)}.", (
            "En UTC, une commande passée entre minuit et 1 h à Cotonou est rangée la veille : chaque jour perd sa première heure "
            f"et gagne celle du lendemain. Le {jour_fr(jour)} totalise {fcfa(jours[code].get(jour))} en UTC, "
            f"alors que la référence place le record le {jour_fr(jour_ref)} ({fcfa(jours[reference].get(jour_ref))}).")

    if code == "7_imputation_moyenne":
        note, note_ref = formater("note_moyenne", v["note_moyenne"]), formater("note_moyenne", r["note_moyenne"])
        lecon = ("Pas de phrase trompeuse chiffrée ici, mais une leçon : imputer ne corrige pas un biais MNAR, et la moyenne dilue "
                 "les mécontents. Avec l'imputation, la part de clients insatisfaits vaut "
                 f"{dire('part_insatisfaits_pct', v['part_insatisfaits_pct'])} "
                 f"(au lieu de {dire('part_insatisfaits_pct', r['part_insatisfaits_pct'])}) et la note moyenne "
                 + (f"ne bouge pas ({note})." if note == note_ref else f"vaut {note} au lieu de {note_ref}."))
        if oracle is None:
            return None, lecon + " (Fichier data/oracle/note_vraie.csv absent : impossible de chiffrer la vraie note.)"
        vraie_note, vraie_part = verite(frames[reference], oracle)
        return None, lecon + (
            f" Or, d'après l'oracle (les vraies notes des commandes livrées ou retournées), la vraie note moyenne est de "
            f"{formater('note_moyenne', vraie_note)} et la vraie part de clients insatisfaits (notes de 1 ou 2) est de "
            f"{dire('part_insatisfaits_pct', vraie_part)} : "
            "les mécontents notent moins souvent, leurs notes manquent, et les remplacer par la moyenne les efface.")

    return None, None


def onglet_raconter(frames, kpis, ecarts, lignes, reference, oracle):
    st.subheader("Ce que chaque scénario permettrait de raconter")
    autres = [code for code in lignes if code != reference]
    if len(frames) == 1:
        st.info("Un seul scénario trouvé : lancez la partie 7 du notebook pour produire les autres scénarios "
                "(ou déposez un Parquet dans la barre latérale).")
        return
    if not autres:
        st.info("Ajoutez au moins un autre scénario à comparer (barre latérale) pour lire ce qu'il change.")
        return
    st.caption("Pour chaque scénario : le meilleur jour s'il change, puis ses trois plus gros écarts à la référence (écart relatif, "
               "en valeur absolue, parmi : " + ", ".join(LIBELLES[c][0] for c in A_RACONTER) + "). "
               "Viennent ensuite la phrase trompeuse qu'il permettrait d'écrire et pourquoi elle est fausse.")
    if reference != "1_recommande":
        st.info("Les phrases trompeuses et leurs explications sont calculées par rapport au scénario recommandé : "
                "choisissez « Recommandé (le cours) » comme scénario de référence pour les lire.")
    jours = {code: ca_par_jour(frames[code]) for code in [reference, *autres]}
    for code in autres:
        st.markdown(f"#### {nom_scenario(code)}")
        st.markdown(phrase_ecarts(code, reference, kpis, ecarts, jours))
        st.markdown(phrase_tests(kpis.loc[code]))
        if reference != "1_recommande":
            continue
        phrase, explication = histoire(code, reference, kpis, ecarts, frames, jours, oracle)
        if phrase:
            st.warning(f"Phrase trompeuse qu'il permettrait d'écrire : « {phrase} »", icon="⚠️")
            st.markdown(explication)
        elif explication:
            st.info(explication, icon="💡")
        else:
            st.caption("Pas de phrase trompeuse prévue pour ce scénario : avant d'écrire une conclusion, "
                       "vérifiez qu'elle ne repose pas sur l'un de ces écarts.")


# ---------------------------------------------------------------- journal
def onglet_journal(journal, chemin_journal, chemin_progression, kpis):
    st.subheader("Journal de nettoyage du scénario recommandé")
    if journal is None or "étape" not in journal.columns:
        st.info("Fichier output/journal_nettoyage.csv introuvable : lancez d'abord la partie 6 du notebook, "
                "qui l'écrit avec journal.exporter.")
    else:
        etapes = list(dict.fromkeys(journal["étape"]))
        choix = st.multiselect("Étapes affichées", etapes, default=etapes, key="journal_etapes")
        filtre = journal[journal["étape"].isin(choix)]
        st.dataframe(filtre.style.format({"lignes": nombre}) if "lignes" in filtre.columns else filtre, hide_index=True, width="stretch")
        st.caption(f"{nombre(len(filtre))} décision(s) affichée(s) sur {nombre(len(journal))}.")

    st.markdown("**Télécharger**")
    gauche, milieu, droite = st.columns(3)
    if chemin_journal.exists():
        gauche.download_button("Journal de nettoyage (CSV)", chemin_journal.read_bytes(), file_name="journal_nettoyage.csv", mime="text/csv")
    if chemin_progression.exists():
        milieu.download_button("Progression des indicateurs (CSV)", chemin_progression.read_bytes(), file_name="progression_kpis.csv",
                               mime="text/csv")
    droite.download_button("Indicateurs des scénarios (CSV)", kpis.to_csv(index_label="scenario").encode("utf-8"),
                           file_name="kpis_tableau_de_bord.csv", mime="text/csv")


# ---------------------------------------------------------------- la page
def ajouter_depot(frames, kpis):
    """Barre latérale : un Parquet déposé devient le scénario « mon_scenario »."""
    depot = st.sidebar.file_uploader("Ajouter un scénario (Parquet)", type=["parquet"],
                                     help="Il apparaît sous le nom « mon_scenario ». Des dates sans fuseau sont lues à l'heure de Cotonou.")
    if depot is None:
        return frames, kpis
    df, erreur = lire_depot(depot.getvalue())
    if erreur is None:
        try:
            ligne = tableau_kpis({"mon_scenario": indicateurs(df)})
        except Exception as e:  # un fichier inattendu ne doit pas faire tomber le tableau de bord
            erreur = f"Indicateurs incalculables sur ce fichier ({type(e).__name__})."
    if erreur:
        st.sidebar.error(f"« {depot.name} » n'a pas été ajouté. {erreur}")
        return frames, kpis
    st.sidebar.success(f"« {depot.name} » ajouté sous le nom « mon_scenario » ({nombre(len(df))} lignes).")
    return {**frames, "mon_scenario": df}, (ligne if kpis.empty else pd.concat([kpis, ligne]))


def barre_laterale(codes, zone):
    with zone:
        st.header("Réglages")
        defaut = "1_recommande" if "1_recommande" in codes else codes[0]
        # Les clés gardent la référence et la sélection quand la liste change (Parquet déposé) ; un nouveau mon_scenario est coché.
        reference = st.selectbox("Scénario de référence", codes, index=codes.index(defaut), format_func=nom_scenario,
                                 help="Les écarts sont calculés par rapport à ce scénario.", key="reference")
        if "mon_scenario" in codes and "mon_scenario" not in st.session_state.get("codes_vus", codes) and "compares" in st.session_state:
            st.session_state["compares"] = [*st.session_state["compares"], "mon_scenario"]
        st.session_state["codes_vus"] = codes
        compares = st.multiselect("Scénarios comparés", codes, default=None if "compares" in st.session_state else codes,
                                  format_func=nom_scenario, key="compares")
        cles = st.multiselect("Indicateurs affichés", list(LIBELLES), default=INDICATEURS_DEFAUT, format_func=lambda c: LIBELLES[c][0])
    return reference, compares, cles


def main():
    st.set_page_config(page_title="Nettoyage des données · comparer les décisions", page_icon="🧹", layout="wide")
    st.title("Nettoyage des données · comparer les décisions")
    st.markdown("Le **même fichier brut**, nettoyé avec **plusieurs jeux de décisions** : chaque scénario donne d'autres chiffres. "
                "Comparez-les au scénario de référence pour voir ce que chaque décision change.")

    dossier_scenarios, dossier_rapports, chemin_oracle = dossiers()
    zone_reglages = st.sidebar.container()
    mtime = dates_de_modification(dossier_scenarios)
    frames, ecartes, kpis = {}, {}, pd.DataFrame()
    if mtime:
        try:
            frames, ecartes = lire_scenarios(str(dossier_scenarios), mtime)
            if frames:
                kpis = calculer_indicateurs(str(dossier_scenarios), mtime)
        except Exception as e:  # Parquet abîmé : on explique au lieu de planter
            st.error(f"Impossible de lire output/scenarios/ ({type(e).__name__} : {e}).")
            frames, kpis = {}, pd.DataFrame()
    for nom, raison in ecartes.items():
        st.sidebar.warning(f"« {nom} » est écarté : {raison}")
    frames, kpis = ajouter_depot(frames, kpis)
    if not frames:
        st.info("Aucun scénario trouvé dans output/scenarios/. Lancez d'abord la partie 7 du notebook : elle enregistre "
                f"output/scenarios/{FICHIER_CONSOLIDE}. Vous pouvez aussi déposer un Parquet dans la barre latérale.")
        st.stop()

    source = FICHIER_CONSOLIDE if (dossier_scenarios / FICHIER_CONSOLIDE).exists() else "un Parquet par scénario"
    st.sidebar.caption(f"Source : output/scenarios/ ({source}) · {len(frames)} scénario(s).")
    reference, compares, cles = barre_laterale(list(frames), zone_reglages)
    lignes = [reference] + [code for code in compares if code != reference]
    ecarts = comparer(kpis, reference)

    chemin_progression = dossier_rapports / "progression_kpis.csv"
    chemin_journal = dossier_rapports / "journal_nettoyage.csv"
    onglets = st.tabs(["Vue d'ensemble", "Cascade du nettoyage", "Zoom", "Raconter", "Journal"])
    with onglets[0]:
        onglet_vue_ensemble(kpis, ecarts, lignes, cles, reference)
    with onglets[1]:
        onglet_cascade(lire_rapport(chemin_progression), cles)
    with onglets[2]:
        onglet_zoom(frames, kpis, lignes, reference, cles)
    with onglets[3]:
        onglet_raconter(frames, kpis, ecarts, lignes, reference, lire_oracle(chemin_oracle))
    with onglets[4]:
        onglet_journal(lire_rapport(chemin_journal, texte_brut=True), chemin_journal, chemin_progression, kpis)


if __name__ == "__main__":
    main()
