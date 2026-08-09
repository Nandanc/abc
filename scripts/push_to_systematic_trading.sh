#!/usr/bin/env bash
# Point local repo at systematic_trading after renaming on GitHub.
# GitHub: Settings → Repository name → systematic_trading

set -euo pipefail
cd "$(dirname "$0")/.."

REPO_URL="https://github.com/Nandanc/systematic_trading.git"

git remote set-url origin "$REPO_URL"
git push -u origin main
echo "Done: https://github.com/Nandanc/systematic_trading"
