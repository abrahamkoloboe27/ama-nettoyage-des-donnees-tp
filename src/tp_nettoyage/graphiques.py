"""Graphiques matplotlib aux couleurs de l'AMA : cascade du nettoyage et comparaison des scénarios."""
import matplotlib.pyplot as plt
import pandas as pd

from .config import COULEURS
from .kpis import LIBELLES, nombre
from .scenarios import LIBELLES_SCENARIOS

COULEURS_ETAPES = [COULEURS["marine"], COULEURS["types"], COULEURS["types"], COULEURS["doublons"],
                   COULEURS["aberrantes"], COULEURS["manquants"]]


def _valeurs(table, cle):
    valeurs = pd.to_numeric(table[cle], errors="coerce")
    return valeurs / 1e6 if cle == "ca_fcfa" else valeurs


def _etiquette(v, cle):
    if pd.isna(v):
        return "  incalculable"
    forme = "entier" if cle == "tests_qualite" else LIBELLES[cle][2]
    decimales = {"entier": 0, "millions": 1}.get(forme)
    return f" {nombre(v, int(forme) if decimales is None else decimales)}"


def _style(ax):
    for cote in ["top", "right"]:
        ax.spines[cote].set_visible(False)
    ax.tick_params(colors=COULEURS["texte"])
    ax.grid(axis="x", color=COULEURS["bleu_clair"])
    ax.set_axisbelow(True)


def tracer_progression(suivi, indicateurs=("ca_fcfa", "prix_moyen_fcfa", "clients_par_telephone", "tests_qualite")):
    """Un panneau par indicateur : sa valeur à chaque point d'étape (barre vide = incalculable)."""
    table = suivi.table() if hasattr(suivi, "table") else suivi
    fig, axes = plt.subplots(1, len(indicateurs), figsize=(4.2 * len(indicateurs), 3.6), squeeze=False)
    for ax, cle in zip(axes[0], indicateurs):
        valeurs = _valeurs(table, cle)
        titre = "Tests qualité (sur 8)" if cle == "tests_qualite" else LIBELLES[cle][0]
        couleurs = [COULEURS_ETAPES[i % len(COULEURS_ETAPES)] for i in range(len(valeurs))]
        ax.barh(range(len(valeurs)), valeurs.fillna(0), color=couleurs)
        for i, v in enumerate(valeurs):
            ax.text(0 if pd.isna(v) else v, i, _etiquette(v, cle), va="center", fontsize=8, color=COULEURS["texte"])
        ax.set_yticks(range(len(valeurs)), table.index if ax is axes[0][0] else [""] * len(valeurs))
        ax.invert_yaxis()
        ax.set_title(titre + (" (M FCFA)" if cle == "ca_fcfa" else ""), color=COULEURS["marine"], fontsize=10, loc="left")
        _style(ax)
    fig.suptitle("Cascade du nettoyage : chaque étape change les indicateurs", color=COULEURS["marine"], fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    return fig


def tracer_scenarios(kpis_df, indicateurs=("ca_fcfa", "prix_moyen_fcfa", "clients_par_telephone", "note_moyenne"),
                     reference="1_recommande"):
    """Un panneau par indicateur : une barre par scénario, la référence en bleu marine et en pointillés."""
    fig, axes = plt.subplots(1, len(indicateurs), figsize=(4.2 * len(indicateurs), 0.45 * len(kpis_df) + 1.6), squeeze=False)
    noms = [LIBELLES_SCENARIOS.get(s, s) for s in kpis_df.index]
    for ax, cle in zip(axes[0], indicateurs):
        valeurs = _valeurs(kpis_df, cle)
        couleurs = [COULEURS["marine"] if s == reference else COULEURS["types"] for s in kpis_df.index]
        ax.barh(range(len(valeurs)), valeurs.fillna(0), color=couleurs)
        for i, v in enumerate(valeurs):
            ax.text(0 if pd.isna(v) else v, i, _etiquette(v, cle), va="center", fontsize=8, color=COULEURS["texte"])
        if reference in kpis_df.index and not pd.isna(valeurs[reference]):
            ax.axvline(valeurs[reference], color=COULEURS["marine"], linestyle="--", linewidth=1)
        ax.set_yticks(range(len(valeurs)), noms if ax is axes[0][0] else [""] * len(valeurs))
        ax.invert_yaxis()
        ax.set_title(LIBELLES[cle][0] + (f" ({LIBELLES[cle][1]})" if LIBELLES[cle][1] else ""),
                     color=COULEURS["marine"], fontsize=10, loc="left")
        _style(ax)
    fig.suptitle("Même fichier, plusieurs jeux de décisions", color=COULEURS["marine"], fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    return fig
