#!/bin/zsh
# Zet de nachtelijke verzamelaar aan (of vernieuwt hem) voor de ingelogde gebruiker.
set -eu
LABEL=nl.businessdatasolutions.ev-wiki.verzamelaar
DOEL="$HOME/Library/LaunchAgents/$LABEL.plist"
cp "${0:A:h}/$LABEL.plist" "$DOEL"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DOEL"
launchctl print "gui/$(id -u)/$LABEL" | grep -E "state|path" | head -3
