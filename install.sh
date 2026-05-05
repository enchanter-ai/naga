#!/usr/bin/env bash
# Naga installer. Sub-plugins coordinate through the enchanted-mcp event bus;
# the `full` meta-plugin pulls them all in via one dependency-resolution pass.
set -euo pipefail

REPO="git@github.com:enchanter-ai/naga.git"
PLUGIN_HOME_DIR="${PLUGIN_HOME_DIR:-$HOME/.naga}"

step() { printf "\n\033[1;36m> %s\033[0m\n" "$*"; }
ok()   { printf "  \033[32m+\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*" >&2; }

step "Naga installer"

# 1. Clone the monorepo so shared/scripts/*.py are available locally.
if [[ -d "$PLUGIN_HOME_DIR/.git" ]]; then
  git -C "$PLUGIN_HOME_DIR" pull --ff-only --quiet
  ok "Updated existing clone at $PLUGIN_HOME_DIR"
else
  git clone --depth 1 --quiet "$REPO" "$PLUGIN_HOME_DIR"
  ok "Cloned to $PLUGIN_HOME_DIR"
fi

# 2. Pre-flight git check.
if ! command -v git >/dev/null 2>&1; then
  warn "git not found on PATH — Naga requires git"
  exit 1
fi
ok "git present"

# 3. Pre-flight python check (stdlib only — no pip).
if ! command -v python3 >/dev/null 2>&1; then
  warn "python3 not found on PATH — Naga hooks require Python 3.8+"
  exit 1
fi
ok "python3 present"

cat <<'EOF'

  Naga ships as a 7-plugin marketplace. Each sub-plugin owns one engine or
  one orthogonal concern. The `full` meta-plugin lists them all as
  dependencies so one install pulls in the whole chain.

  Finish in Claude Code with TWO commands:

    /plugin marketplace add enchanter-ai/naga
    /plugin install full@naga

  Verify with:   /plugin list
  Expected:      full + 6 sub-plugins installed under the naga marketplace.

EOF
