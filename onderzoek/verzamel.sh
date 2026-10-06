#!/bin/zsh
# Start de verzamelaar (CLAUDE.md §Verzamelaar). Aangeroepen door launchd elke nacht, of met de hand.
# Argumenten gaan door naar verzamelaar.py (bijv. --droog, --verken, --max 4).
set -u
REPO="${0:A:h:h}"
cd "$REPO" || exit 1
UV="${UV:-$HOME/.local/bin/uv}"
LOGFILE="onderzoek/logs/$(date +%Y-%m-%d).log"
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') verzamelaar $*"
  "$UV" run --no-project --with-requirements .claude/skills/youtube-transcript-skill/requirements.txt \
    python -u onderzoek/verzamelaar.py "$@"
  echo "=== exit $?"
  # Maandcijfers van eu-evs.com (intern, raw/data/ is gitignored); één keer per maand, en een
  # fout hier houdt de verzamelaar niet tegen.
  "$UV" run --no-project --with requests python -u onderzoek/eu_evs.py
  echo "=== eu-evs exit $?"
} >> "$LOGFILE" 2>&1
