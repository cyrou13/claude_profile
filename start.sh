#!/usr/bin/env bash
# start.sh — Lance claude-profile (install + dashboard)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${CLAUDE_PROFILE_PORT:-8741}"
HOST="${CLAUDE_PROFILE_HOST:-127.0.0.1}"

# Couleurs
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RESET='\033[0m'

info() { echo -e "${CYAN}[claude-profile]${RESET} $*"; }
ok()   { echo -e "${GREEN}[claude-profile]${RESET} $*"; }

# --- Pre-requis ---

if ! command -v uv &>/dev/null; then
    echo "erreur: uv n'est pas installe. Installe-le avec: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# --- Install deps ---

info "Installation des dependances..."
uv sync --quiet 2>/dev/null || uv sync

# --- Config check ---

CONFIG_FILE="$HOME/.config/claude-profile/config.toml"
if [ ! -f "$CONFIG_FILE" ]; then
    info "Creation de la config par defaut dans $CONFIG_FILE"
    mkdir -p "$(dirname "$CONFIG_FILE")"
    cat > "$CONFIG_FILE" << 'TOML'
[general]
claude_home = "~/.claude"
sync_repo = "~/Documents/dev/claude-profile-sync"

[sync]
include = ["CLAUDE.md", "settings.json", "skills/", "agents/", "commands/"]
exclude = ["settings.local.json", "sessions/", "history.jsonl", "cache/", "debug/", "telemetry/", "stats-cache.json", "usage-data/", "plans/"]
scan_dirs = ["~/Documents/dev"]

[veille]
check_interval_hours = 24
github_repos = ["anthropics/claude-code", "modelcontextprotocol/servers", "anthropics/courses"]

[dashboard]
port = 8741

# Ajouter tes profils :
# [[profiles]]
# name = "work"
# projects = ["project-a", "project-b"]
# description = "Projets pro"
# claude_md_overlay = """
# ## Contexte pro
# - Focus production
# """
TOML
    ok "Config creee. Edite $CONFIG_FILE pour ajouter tes profils."
fi

# --- Kill ancien process sur le port ---

if lsof -ti:"$PORT" &>/dev/null; then
    info "Arret du process existant sur le port $PORT..."
    lsof -ti:"$PORT" | xargs kill 2>/dev/null || true
    sleep 1
fi

# --- Lancement ---

ok "Dashboard disponible sur http://$HOST:$PORT"
ok "Ctrl+C pour arreter"
echo ""

exec uv run claude-profile dashboard --port "$PORT" --host "$HOST"
