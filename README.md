# TD · Nettoyage des données — AMA

Séance de TD du module **« Nettoyage des données »** (UE Ingénierie des données, AMA · module 13 · cours 3 h + TD 3 h, le 14 octobre 2026).

**Objectif :** reprendre tout le nettoyage du cours sur un vrai fichier, l'exécuter et le commenter. On explore le fichier, on rend types et formats cohérents, puis on traite les doublons, les valeurs aberrantes et les valeurs manquantes. On prouve ensuite la qualité par des tests, on exporte, et on mesure comment chaque décision de nettoyage change les chiffres présentés à la direction.

Le notebook suit un rythme simple : un paragraphe court, un bout de code, la sortie, puis une ou deux phrases pour l'interpréter. Les 💬 marquent les questions à discuter en salle, et les **points 📊** montrent ce que chaque étape a changé dans les indicateurs et les tests qualité.

---

## Le fichier : les commandes de septembre 2026

Tout le TD part du fichier du cours, `data/raw/commandes_brutes.csv`. C'est l'export brut d'une boutique en ligne de Cotonou : 50 312 lignes et 17 colonnes, soit 50 000 commandes et 312 lignes en double. On y retrouve les anomalies vues en cours :
- des prix en texte (« 25 500 FCFA ») ;
- des dates dans quatre formats, et en UTC ;
- les villes écrites de 25 façons pour 5 villes (« Ctn », « COTONOU »…) ;
- des téléphones mal formés ;
- des doublons ;
- des notes de 50 sur 5 ;
- des valeurs manquantes déguisées.

`data/SHA256SUMS.txt` donne son empreinte : le notebook vérifie au démarrage que c'est bien le fichier du cours. `data/oracle/note_vraie.csv` donne la vraie note de chaque commande livrée. Ce fichier est impossible à obtenir dans la vraie vie : il sert seulement à mesurer le biais des notes manquantes.

## Le parcours

Un seul notebook : [`notebooks/TD_nettoyage_des_donnees.ipynb`](notebooks/TD_nettoyage_des_donnees.ipynb).

| Partie | Ce que l'on fait | Slides | Durée |
|---|---|---|---|
| 1 · Explorer | Charger sans se faire piéger, les 10 commandes du premier contact, lire un `describe()`, le profil des colonnes | 8 à 11 | 20 min |
| 2 · Types et formats | Prix (le piège de l'espace insécable), poids, dates (formats, fenêtre, fuseau), référentiels, encodage, téléphones, e-mails | 12 à 15 | 30 min |
| 3 · Doublons | Doublons exacts, versions d'une commande, doubles clics, jointure piégée, clients approchés | 16 à 18 | 20 min |
| 4 · Valeurs aberrantes | Règles métier, z-score contre IQR et MAD, comparaison des détecteurs, Mahalanobis, décisions | 19 à 25 | 30 min |
| 5 · Valeurs manquantes | Manquants déguisés, MCAR, MAR ou MNAR, le biais des notes mesuré, l'arbre de décision, imputer sans fuite | 26 à 30 | 25 min |
| 6 · Prouver et exporter | Les tests qualité, le journal, Parquet contre CSV | 31 à 33 | 15 min |
| 7 · Comparer les décisions | Le même fichier nettoyé de 8 façons, et le tableau de bord | — | 30 min |

Le **[plan de la séance](docs/plan_tp.md)** donne le minutage et ce qu'il faut faire remarquer à chaque étape.

---

## Installation

### 1. Récupérer le dépôt

```bash
git clone https://github.com/abrahamkoloboe27/ama-nettoyage-des-donnees-tp.git
cd ama-nettoyage-des-donnees-tp
```

### 2. Installer les dépendances (Python ≥ 3.11)

Avec **uv** (recommandé) :

```bash
uv sync
```

Ou avec **pip**, dans un environnement virtuel :

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Lancer Jupyter

```bash
uv run jupyter lab               # ou simplement : jupyter lab (environnement pip activé)
```

Ouvrez `notebooks/TD_nettoyage_des_donnees.ipynb`. Le notebook complet s'exécute en moins d'une minute.

### 4. Le tableau de bord (partie 7)

Une fois la partie 7 exécutée, dans un **second terminal**, à la racine du dépôt :

```bash
uv run streamlit run dashboard/app.py
```

Sans uv, l'environnement activé : `streamlit run dashboard/app.py`.

Il compare les 8 versions nettoyées du fichier en cinq onglets :
- **Vue d'ensemble** : les indicateurs de chaque version ;
- **Cascade du nettoyage** : les points d'étape ;
- **Zoom** : le chiffre d'affaires par ville, par catégorie et par jour, et la distribution des prix ;
- **Raconter** : les phrases trompeuses que chaque mauvaise décision permettrait d'écrire ;
- **Journal** : les décisions de nettoyage.

---

## Structure du dépôt

```
├── notebooks/
│   └── TD_nettoyage_des_donnees.ipynb   # le TD, exécuté
├── data/
│   ├── raw/commandes_brutes.csv         # le fichier du cours (ne jamais le modifier)
│   ├── oracle/note_vraie.csv            # les vraies notes (biais des manquants)
│   └── SHA256SUMS.txt                   # empreintes des deux fichiers
├── src/tp_nettoyage/                    # petits outils : journal, suivi des indicateurs, scénarios, graphiques
├── dashboard/app.py                     # le tableau de bord Streamlit
├── output/                              # fichiers produits par le notebook (ignorés par Git)
├── docs/plan_tp.md                      # déroulé de la séance de 3 h
├── pyproject.toml / uv.lock
└── requirements.txt
```

## Les données

Les commandes sont **fictives**. Elles ont été générées pour l'enseignement, avec des anomalies injectées volontairement, et reprennent la boutique en ligne de Cotonou des modules « Sources de données » et « Formats de données ».
