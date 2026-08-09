#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

pip3 install --user -r requirements.txt
