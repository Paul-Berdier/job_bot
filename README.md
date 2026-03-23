# 🤖 Job Bot – Candidatures Automatiques avec IA

Bot de candidature automatique multi-plateformes avec génération de lettres de motivation par IA (Claude).

## ✨ Fonctionnalités

- **3 plateformes** : Indeed, Welcome to the Jungle, HelloWork
- **Recherche automatique** par mots-clés + localisation
- **Candidature directe** depuis une URL
- **Lettres de motivation IA** personnalisées par offre (Claude Anthropic)
- **Anti-détection** : délais aléatoires, frappe simulée, mouvements de souris naturels
- **Base de données** SQLite : historique complet, zéro doublon
- **Logs** colorés + captures d'écran en cas d'erreur
- **Mode dry-run** : tester sans postuler

---

## 🛠️ Installation

### 1. Prérequis

- Python 3.10+
- Un compte sur chaque plateforme (Indeed, WTTJ, HelloWork)
- Une clé API Anthropic → https://console.anthropic.com

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configurer

```bash
# Copier et éditer la config
cp config.yaml config.local.yaml   # optionnel pour garder config.yaml propre
nano config.yaml
```

Remplir dans `config.yaml` :
- `anthropic_api_key` : votre clé `sk-ant-...`
- `profile` : vos informations personnelles
- `profile_summary` : votre résumé pro (sert à l'IA pour personnaliser les lettres)
- `platforms.*.email/password` : identifiants pour chaque plateforme
- `search.keywords` et `search.location`

### 4. Déposer votre CV

Placer votre CV PDF dans `data/cv.pdf` (ou modifier `profile.cv_path` dans la config).

---

## 🚀 Utilisation

### Recherche + candidatures automatiques

```bash
python main.py run
```

```bash
# Tester sans postuler réellement
python main.py run --dry-run

# Limiter à une plateforme
python main.py run --platform indeed
python main.py run --platform wttj
python main.py run --platform hellowork
```

### Postuler à une offre précise (URL directe)

```bash
python main.py apply "https://fr.indeed.com/viewjob?jk=abc123"
python main.py apply "https://www.welcometothejungle.com/fr/companies/xxx/jobs/yyy"
python main.py apply "https://www.hellowork.com/fr-fr/emploi/xxx.html"
```

### Voir les statistiques

```bash
python main.py stats
```

### Vérifier la configuration

```bash
python main.py config
```

---

## 📁 Structure du projet

```
job-bot/
├── main.py                       # Point d'entrée CLI
├── config.yaml                   # Configuration (à remplir)
├── requirements.txt
│
├── scrapers/
│   ├── base_scraper.py           # Classe abstraite + modèle JobOffer
│   ├── indeed_scraper.py         # Scraper Indeed
│   ├── wttj_scraper.py           # Scraper Welcome to the Jungle
│   └── hellowork_scraper.py      # Scraper HelloWork
│
├── applicator/
│   ├── base_applicator.py        # Classe abstraite
│   ├── indeed_applicator.py      # Candidature Indeed
│   ├── wttj_applicator.py        # Candidature WTTJ
│   └── hellowork_applicator.py   # Candidature HelloWork
│
├── ai/
│   └── cover_letter.py           # Génération IA des lettres (Claude)
│
├── utils/
│   ├── db.py                     # Base de données SQLite (historique)
│   ├── logger.py                 # Logger Rich coloré
│   └── human_behavior.py         # Simulation comportement humain
│
├── data/
│   ├── cv.pdf                    # Votre CV ← À PLACER ICI
│   └── applications.db           # BDD auto-générée
│
└── logs/                         # Logs + screenshots erreurs
```

---

## ⚙️ Paramètres importants

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| `bot.headless` | `true` = invisible, `false` = voir navigateur | `false` |
| `bot.min_delay_seconds` | Délai minimum entre actions | `3` |
| `bot.max_delay_seconds` | Délai maximum entre actions | `8` |
| `search.max_jobs_per_run` | Candidatures max par lancement | `20` |
| `filters.skip_keywords` | Mots à ignorer dans les offres | `["stage", ...]` |

---

## ⚠️ Notes importantes

### Anti-bot
- Les plateformes détectent les bots. Le bot simule un comportement humain mais **aucune garantie**.
- Utiliser `headless: false` au début pour surveiller le comportement.
- En cas de CAPTCHA, le bot s'arrête et vous devez intervenir manuellement.
- Ne pas lancer trop de candidatures d'un coup (max 20/jour recommandé).

### CGU
- L'automatisation peut être contraire aux CGU de certaines plateformes.
- Utilisation à vos risques et périls.

### Sélecteurs DOM
- Les sites changent régulièrement leur DOM. Si un scraper cesse de fonctionner,
  inspectez les sélecteurs CSS dans les fichiers `scrapers/` et `applicator/`.

---

## 🔧 Dépannage

**Le bot ne se connecte pas**
→ Vérifier email/password dans config.yaml
→ Essayer headless: false pour voir ce qui se passe
→ Certaines connexions nécessitent une 2FA manuelle la première fois

**La lettre de motivation est générique**
→ Enrichir `profile_summary` dans config.yaml avec plus de détails

**Erreur "selector not found"**
→ Le DOM du site a changé. Inspecter l'élément dans le navigateur et mettre à jour le sélecteur.

---

## 📊 Exemple de sortie

```
╭─────────────────────────────────────╮
│  🤖 JOB BOT                         │
│  Candidatures automatiques avec IA  │
╰─────────────────────────────────────╯

[10:23:15] INFO  [Indeed] Recherche : Développeur Python | Paris
[10:23:18] INFO  [Indeed] 15 offres trouvées
[10:23:19] INFO  🤖 Génération lettre pour Dev Backend Python @ Startup XYZ...
[10:23:21] INFO  ✅ Lettre générée
✅ [1/20] Dev Backend Python @ Startup XYZ
✅ [2/20] Ingénieur Python @ FinTech ABC
...
🎉 Session terminée : 12 candidature(s) envoyée(s)
```
