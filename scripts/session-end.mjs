#!/usr/bin/env node
// Fired on Stop hook (configured in .claude/settings.json) — at the end of
// every assistant turn. v0.4 keeps this minimal: if any wiki/**/*.md file is
// modified or untracked, re-run scripts/graph-export.mjs so wiki/.graph.json
// stays fresh; otherwise exit silently. Always exits 0.
//
// Per CLAUDE.md §Hooks, this script must NOT edit any wiki content page.
// The only side effect permitted here is the gitignored wiki/.graph.json
// being rewritten by graph-export.
//
// The "append a session-summary log entry" idea from llm-wiki-v2-plan.md is
// deliberately deferred — Stop fires per-turn (not per-session) so per-turn
// log entries would be too noisy to be useful. Manual log writing remains
// the convention.

import { spawnSync } from "node:child_process"
import { join, dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = resolve(SCRIPT_DIR, "..")

// Check whether the working tree has any uncommitted wiki/**/*.md changes
const status = spawnSync("git", ["status", "--porcelain", "wiki/"], {
  cwd: REPO_ROOT,
  encoding: "utf8",
})

if (status.status !== 0) {
  // git unavailable or repo problem — exit silently
  process.exit(0)
}

const lines = status.stdout.split("\n").filter(Boolean)
const wikiMdChanged = lines.some((line) => /\.md\s*$/.test(line))

if (!wikiMdChanged) {
  process.exit(0)
}

// Wiki content changed this turn (or earlier in the session) — refresh the
// derived graph so .graph.json reflects current frontmatter relationships.
const graph = spawnSync("node", [join(SCRIPT_DIR, "graph-export.mjs")], {
  cwd: REPO_ROOT,
  encoding: "utf8",
})

if (graph.status !== 0) {
  // Don't surface graph-export failures here — this is an idle background
  // refresh; if there's a real problem the user will hit it during a manual
  // run of graph-export.mjs.
  process.exit(0)
}

process.exit(0)
