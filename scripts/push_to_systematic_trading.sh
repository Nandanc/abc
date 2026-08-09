#!/usr/bin/env bash
# Create github.com/Nandanc/systematic_trading and push this project.
# Requires GitHub CLI (gh) logged in with repo create permission.

set -euo pipefail
cd "$(dirname "$0")/.."

REPO="Nandanc/systematic_trading"

if gh repo view "$REPO" >/dev/null 2>&1; then
  echo "Repository $REPO already exists."
else
  echo "Creating $REPO..."
  gh repo create "$REPO" \
    --public \
    --description "Systematic trading backtests — Golden Cross / Death Cross on Nifty 500"
fi

if git remote get-url systematic_trading >/dev/null 2>&1; then
  git remote set-url systematic_trading "https://github.com/${REPO}.git"
else
  git remote add systematic_trading "https://github.com/${REPO}.git"
fi

git push -u systematic_trading main
echo "Done: https://github.com/${REPO}"
