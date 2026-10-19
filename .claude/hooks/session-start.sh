#!/usr/bin/env bash
# V cloudové session (claude.ai/code) nainstaluje Python závislosti. Lokálně nedělá nic.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"
python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt
echo "webstats: závislosti nainstalovány"
