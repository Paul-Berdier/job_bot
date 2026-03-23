#!/bin/bash
# =============================================================
#  Job Bot – Script d'installation automatique
# =============================================================

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║     🤖  JOB BOT – Installation       ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── Vérification Python ────────────────────────────────────────
echo -e "${CYAN}[1/5] Vérification de Python...${NC}"
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ Python 3 non trouvé. Installez Python 3.10+${NC}"
    exit 1
fi
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✅ Python ${PY_VERSION} détecté${NC}"

# ── Environnement virtuel ──────────────────────────────────────
echo -e "${CYAN}[2/5] Création de l'environnement virtuel...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}✅ Virtualenv créé dans .venv/${NC}"
else
    echo -e "${YELLOW}⚠️  .venv/ existe déjà, réutilisation${NC}"
fi

# Activer le venv
source .venv/bin/activate

# ── Dépendances Python ─────────────────────────────────────────
echo -e "${CYAN}[3/5] Installation des dépendances Python...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✅ Dépendances installées${NC}"

# ── Playwright ─────────────────────────────────────────────────
echo -e "${CYAN}[4/5] Installation de Playwright (Chromium)...${NC}"
playwright install chromium
playwright install-deps chromium 2>/dev/null || true
echo -e "${GREEN}✅ Playwright installé${NC}"

# ── Structure des dossiers ─────────────────────────────────────
echo -e "${CYAN}[5/5] Préparation des dossiers...${NC}"
mkdir -p data logs
touch data/.gitkeep logs/.gitkeep

if [ ! -f "config.yaml" ]; then
    echo -e "${YELLOW}⚠️  config.yaml manquant – vérifiez le fichier de configuration${NC}"
fi

# ── Résumé final ───────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✅  Installation terminée !       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📋 Prochaines étapes :${NC}"
echo ""
echo -e "  1. Éditez ${CYAN}config.yaml${NC} avec vos identifiants et votre profil"
echo -e "  2. Placez votre CV PDF dans ${CYAN}data/cv.pdf${NC}"
echo -e "  3. Activez l'environnement : ${CYAN}source .venv/bin/activate${NC}"
echo ""
echo -e "${YELLOW}🚀 Commandes disponibles :${NC}"
echo ""
echo -e "  ${CYAN}python main.py config${NC}           → Vérifier la configuration"
echo -e "  ${CYAN}python main.py run --dry-run${NC}    → Tester sans postuler"
echo -e "  ${CYAN}python main.py run${NC}              → Lancer les candidatures"
echo -e "  ${CYAN}python main.py apply <URL>${NC}      → Postuler à une URL directe"
echo -e "  ${CYAN}python main.py stats${NC}            → Voir les statistiques"
echo -e "  ${CYAN}python dashboard.py${NC}             → Tableau de bord live"
echo -e "  ${CYAN}python scheduler.py --now --interval 6h${NC}  → Planificateur"
echo ""
