"""Outils du TP : empreinte du fichier, journal de nettoyage et suivi des indicateurs étape par étape."""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .config import BRUT
from .kpis import LIBELLES, calculer_kpis, ecart_pct, formater, formater_ecart
from .qualite import NOMS_TESTS, tests_qualite


def empreinte(chemin=BRUT):
    """Empreinte SHA-256 d'un fichier : elle change dès qu'un seul octet change."""
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def _compter(masque):
    if masque is Ellipsis or masque is None:
        raise TypeError("journal.tracer : le masque est encore à compléter (...) ; donnez une série de booléens ou un nombre")
    if np.isscalar(masque):
        return int(masque)
    s = masque if isinstance(masque, pd.Series) else pd.Series(np.asarray(masque))
    if pd.api.types.is_bool_dtype(s) or s.dtype == object:
        return int(s.astype("boolean").fillna(False).sum())
    return int((s.fillna(0) != 0).sum())                     # masque numérique : 0 = faux, le reste = vrai


class Journal:
    """Trace chaque décision : étape, règle, colonne, nombre de lignes touchées, décision (slide 32).

    Relancer une cellule ne crée pas de doublon : une règle déjà tracée (même étape, même règle,
    même colonne) est mise à jour à sa place.
    """

    COLONNES = ["étape", "règle", "colonne", "lignes", "décision"]

    def __init__(self):
        self.lignes = []

    def tracer(self, etape, regle, colonne, masque, decision):
        ligne = {"étape": etape, "règle": regle, "colonne": colonne,
                 "lignes": _compter(masque), "décision": decision}
        for i, ancienne in enumerate(self.lignes):
            if (ancienne["étape"], ancienne["règle"], ancienne["colonne"]) == (etape, regle, colonne):
                self.lignes[i] = ligne
                return
        self.lignes.append(ligne)

    def table(self):
        return pd.DataFrame(self.lignes, columns=self.COLONNES)

    def exporter(self, chemin):
        chemin = Path(chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        self.table().to_csv(chemin, index=False)
        return chemin

    def __len__(self):
        return len(self.lignes)

    def __repr__(self):
        return f"Journal({len(self)} décision(s))"


def _afficher(objet):
    try:
        from IPython.display import display
        display(objet)
    except ImportError:
        print(objet)


class Suivi:
    """Instantanés des indicateurs métier et des tests qualité, étape après étape."""

    def __init__(self):
        self.lignes = []

    def point(self, etape, df, afficher=True):
        """Calcule les indicateurs et les tests qualité de df, les ajoute à la progression et les affiche."""
        tests = tests_qualite(df)
        huit = tests[NOMS_TESTS]
        ligne = {"étape": etape, **calculer_kpis(df),
                 "tests_qualite": int(huit.sum()),
                 "volumetrie": bool(tests.iloc[-1]),
                 "tests_en_echec": " · ".join(huit.index[~huit.to_numpy(dtype=bool)])}
        for i, ancienne in enumerate(self.lignes):
            if ancienne["étape"] == etape:
                self.lignes[i] = ligne
                break
        else:
            self.lignes.append(ligne)
        if afficher:
            self.afficher(etape)

    def table(self):
        """Une ligne par étape : indicateurs, nombre de tests qualité réussis (sur 8), volumétrie."""
        return pd.DataFrame(self.lignes).set_index("étape") if self.lignes else pd.DataFrame()

    def exporter(self, chemin):
        chemin = Path(chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        self.table().to_csv(chemin)
        return chemin

    def afficher(self, etape=None):
        """Tableau de l'étape : valeur au début, à l'étape précédente, maintenant, et l'écart."""
        if not self.lignes:
            print("Aucun point d'étape pour l'instant.")
            return
        noms = [ligne["étape"] for ligne in self.lignes]
        i = noms.index(etape) if etape in noms else len(noms) - 1
        courant, debut = self.lignes[i], self.lignes[0]
        precedent = self.lignes[i - 1] if i > 0 else None
        colonnes = {}
        if i > 0:
            colonnes[f"début · {debut['étape']}"] = debut
        if precedent is not None and i > 1:
            colonnes[f"précédent · {precedent['étape']}"] = precedent
        colonnes[f"maintenant · {courant['étape']}"] = courant
        tableau = {}
        for nom, ligne in colonnes.items():
            tableau[nom] = {LIBELLES[c][0]: formater(c, ligne[c]) for c in LIBELLES}
        if precedent is not None:
            tableau["écart / précédent"] = {LIBELLES[c][0]: self._ecart(c, courant[c], precedent[c]) for c in LIBELLES}
        vol = "✅" if courant["volumetrie"] else "❌"
        print(f"📊 Point « {courant['étape']} » · tests qualité {courant['tests_qualite']} / 8 · volumétrie {vol}")
        if courant["tests_en_echec"]:
            print(f"   Tests en échec : {courant['tests_en_echec']}")
        _afficher(pd.DataFrame(tableau))

    @staticmethod
    def _ecart(cle, valeur, avant):
        if pd.isna(valeur) != pd.isna(avant):
            return "devient calculable" if pd.isna(avant) else "devient incalculable"
        if LIBELLES[cle][2] == "date":
            if pd.isna(valeur) and pd.isna(avant):
                return ""
            return "=" if valeur == avant else "changé"
        return formater_ecart(ecart_pct(valeur, avant))

    def __len__(self):
        return len(self.lignes)

    def __repr__(self):
        return f"Suivi({len(self)} point(s) d'étape)"
