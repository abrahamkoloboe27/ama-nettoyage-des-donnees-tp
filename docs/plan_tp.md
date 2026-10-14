# Plan du TD « Nettoyage des données » — séance de 3 h

Fiche de déroulé pour l'enseignant, que les étudiants peuvent aussi lire. Le cours a posé la démarche : inspecter, profiler, diagnostiquer, traiter, valider, documenter. Le TD la rejoue de bout en bout sur le fichier du cours, `commandes_brutes.csv`. On exécute, on commente, on discute.

## Objectifs : à la fin du TD, l'étudiant sait…

1. explorer un fichier inconnu et dresser le profil de chaque colonne ;
2. convertir types et formats sans perdre d'information, et **compter** ce qui est perdu ;
3. traiter doublons, valeurs aberrantes et valeurs manquantes en justifiant chaque choix ;
4. prouver la qualité par des tests, et tracer chaque décision dans un journal ;
5. montrer, chiffres à l'appui, comment une décision de nettoyage change les indicateurs présentés à la direction.

---

## Avant la séance

| ✔ | Action | Pourquoi |
|---|---|---|
| ☐ | Demander aux étudiants de cloner le dépôt et de lancer `uv sync` (ou `pip install -r requirements.txt`) **la veille** | L'installation (pandas, Streamlit, scikit-learn) télécharge plusieurs centaines de Mo |
| ☐ | Ouvrir le notebook exécuté au vidéoprojecteur | Les sorties enregistrées servent de plan B si une machine résiste |
| ☐ | Tester `uv run streamlit run dashboard/app.py` sur votre poste, après avoir exécuté le notebook | Le tableau de bord lit les fichiers produits par la partie 7 (`output/`) |

---

## Déroulé de la séance

| Horaire | Partie | Ce que l'on montre | À faire remarquer à la salle |
|---|---|---|---|
| 0:00 – 0:20 | **1 · Explorer** | Lecture avec `dtype` et `na_values`, `sample`, `info`, `describe`, `profil` | Le zéro du téléphone mangé sans `dtype`. 25 écritures pour 5 villes. **Point 0** : 4 indicateurs incalculables, 1 test sur 8, et pourtant un CA qui s'affiche (1 856,8 M FCFA) |
| 0:20 – 0:50 | **2 · Types et formats** | Prix, poids, dates, référentiels, encodage, téléphones, e-mails | **Point 1** : délai moyen de −55,4 jours (dates de 1900). **Point 2** : sans supprimer une ligne, Mobile Money passe de 47,98 % à 54,73 %, Cotonou de 38,58 % à 45,19 % du CA, les clients par téléphone de 24 276 à 17 117 |
| 0:50 – 1:10 | **3 · Doublons** | Exacts, versions, doubles clics, `MergeError`, rapidfuzz | **Point 3** : 50 000 lignes, test d'unicité ✅, CA à 1 910,4 M FCFA, 54 doubles clics marqués (pas supprimés) |
| 1:10 – 1:20 | Pause | | Question de la reprise : une note de 50 sur 5, erreur, extrême ou fraude ? |
| 1:20 – 1:50 | **4 · Valeurs aberrantes** | Règles métier, mini-cas, comparaison des détecteurs, décisions de la slide 25 | **Point 4** : 8 tests sur 8 sans supprimer une ligne ; prix moyen −9,7 % (29 117 → 26 280 FCFA), délai 2,40 jours, note 4,16 → 4,23 |
| 1:50 – 2:15 | **5 · Valeurs manquantes** | Manquants déguisés, MCAR/MAR, oracle MNAR, arbre, imputation sans fuite | Note observée 4,23 contre 4,03 en réalité ; insatisfaits 6,7 % contre 12,1 %. **Point 5** : rien ne bouge, le traitement raisonné n'invente aucun chiffre |
| 2:15 – 2:30 | **6 · Prouver et exporter** | Tests (avec la volumétrie), journal, Parquet contre CSV | Le journal répond à « pourquoi 50 000 et pas 50 312 ? ». Le CSV perd tous les types corrigés, jusqu'au zéro des téléphones |
| 2:30 – 3:00 | **7 · Comparer les décisions** | `nettoyer`, les 8 scénarios, puis le tableau de bord | Faire trouver la phrase trompeuse de chaque scénario, puis l'onglet « Raconter » du tableau de bord |

### Les pièges à commenter

1. **L'espace insécable (partie 2).** Avec `r"\s|FCFA"`, 2 052 prix deviennent NaN **sans aucune erreur** : avec les chaînes de pandas 3 (PyArrow), `\s` ne reconnaît pas `\xa0`. Seul le compteur « présent avant, NaN après » le révèle.
2. **Les dates américaines et le fuseau (partie 2).**
   - Lue en jj/mm, une date mm/jj part dans un autre mois sans erreur ; la fenêtre de septembre tranche (545 dates relues).
   - Rester en UTC range 2 045 commandes la veille ; en partie 7, le meilleur jour passe du 22 au 1er septembre.
3. **L'affectation chaînée.** En pandas 3, `df[masque]["col"] = …` ou `df["col"].fillna(0, inplace=True)` ne modifient rien : seulement un avertissement `ChainedAssignmentError`. Toujours `df.loc[masque, "col"] = …`. Sur un `groupby` de colonne `category`, on écrit `observed=True`.
4. **La `MergeError` (partie 3).** `validate="one_to_one"` refuse la jointure quand une commande est payée en deux fois : c'est la protection voulue. On agrège avant de joindre.
5. **Le `dropna()` global (partie 7).** Il ne garde que 1 956 lignes sur 50 000 et efface toutes les annulations (une commande annulée n'a pas de date de livraison). Pourtant, il passe les 8 tests de la slide 31 : seul le test de **volumétrie** le refuse.

### Les phrases trompeuses de la partie 7

| Scénario | La phrase trompeuse | Pourquoi elle est fausse |
|---|---|---|
| Brut, types convertis | « Nous avons 24 000 clients et Cotonou recule. » | 24 276 clients au lieu de 17 117 : un même numéro écrit de plusieurs façons compte plusieurs fois, et « Ctn » ne compte pas pour Cotonou (38,6 % du CA au lieu de 45,2 %) |
| Doublons gardés | « Septembre a rapporté 1 928,4 M FCFA. » | 9,6 M FCFA comptés deux fois ; le test d'unicité échoue |
| Aberrantes supprimées à l'IQR | « La Téléphonie s'effondre. » | L'IQR sur le prix brut supprime les téléphones, simplement chers : la Téléphonie tombe de 50,6 % à 10,6 % du CA |
| `dropna()` global | « Plus aucune commande annulée en septembre. » | Les annulées n'ont pas de date de livraison : `dropna()` les a toutes supprimées |
| NaN remplacés par 0 | « Quatre clients sur dix sont mécontents. » | Un client qui n'a pas noté devient une note de 0 : 42,2 % d'insatisfaits au lieu de 6,7 % |
| Dates laissées en UTC | « Le record du mois a eu lieu le 1er septembre. » | En heure de Cotonou, le record est le 22 septembre (68,9 M FCFA) |
| Imputation par la moyenne | — | La note reste à 4,23 et les insatisfaits tombent à 4,2 %, alors que la réalité (oracle) est 4,03 et 12,1 % : imputer ne corrige pas un biais MNAR |

### En cas de retard

1. Passer vite sur Mahalanobis (partie 4) et sur les clients approchés (partie 3).
2. Montrer l'imputation sans fuite (partie 5) sans s'y arrêter.
3. Garder du temps pour la partie 7 : c'est elle qui donne du sens à tout le reste.

### Si Streamlit ne démarre pas

Le tableau et les graphiques de la partie 7 du notebook suffisent pour comparer les scénarios. Vous pouvez aussi projeter le tableau de bord depuis votre poste.
