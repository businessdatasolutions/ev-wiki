#!/usr/bin/env node
// Fired on SessionStart hook (configured in .claude/settings.json).
//
// Outputs a brief snapshot of wiki state to stdout — Claude Code feeds that
// stdout back into the conversation as additional context. The intent is to
// give Claude orientation without flooding the session: catalog stats, the
// most recent activity, and any pages flagged by the v0.2 lifecycle layer.
//
// Read-only. Never writes to wiki content pages — see CLAUDE.md §Hooks
// non-negotiable rule.

import { readFile, readdir } from "node:fs/promises"
import { join, dirname, relative } from "node:path"
import { fileURLToPath } from "node:url"
import matter from "gray-matter"
import { checkIndexCompleteness } from "./lint-index-completeness.mjs"

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const WIKI_DIR = join(REPO_ROOT, "wiki")

const RECENT_LOG_ENTRIES = 5
const TARGET_DIRS = ["concepts", "entities", "syntheses", "threads"]
const COUNT_DIRS = [...TARGET_DIRS, "sources"]

async function listMarkdown(dir) {
  try {
    const entries = await readdir(dir, { withFileTypes: true })
    const out = []
    for (const entry of entries) {
      if (entry.isDirectory()) continue
      if (!entry.name.endsWith(".md")) continue
      if (entry.name.startsWith(".")) continue
      out.push(join(dir, entry.name))
    }
    return out
  } catch {
    return []
  }
}

async function countByDir() {
  const counts = {}
  for (const sub of COUNT_DIRS) {
    counts[sub] = (await listMarkdown(join(WIKI_DIR, sub))).length
  }
  return counts
}

const stale = []
const lowConfidence = []

for (const sub of TARGET_DIRS) {
  const dir = join(WIKI_DIR, sub)
  const files = await listMarkdown(dir)
  for (const file of files) {
    const raw = await readFile(file, "utf8")
    const { data } = matter(raw)
    const rel = relative(REPO_ROOT, file)
    if (typeof data.status === "string" && data.status.toLowerCase() === "stale") {
      stale.push(rel)
    }
    if (typeof data.confidence === "number" && data.confidence < 0.5) {
      lowConfidence.push({ rel, confidence: data.confidence })
    }
  }
}

const counts = await countByDir()

// Uncatalogued-page check (see scripts/lint-index-completeness.mjs) — surfaces
// pages that exist on disk but were never given an index.md bullet, the
// silent-omission failure mode discovered 2026-07-04 (28 entity pages).
let indexGapTotal = 0
let indexGapDetail = []
try {
  const { report, totalMissing } = await checkIndexCompleteness()
  indexGapTotal = totalMissing
  indexGapDetail = report.filter((r) => r.missing.length > 0)
} catch {}

// N most recent log.md entries (heading lines only, not full bodies).
// log.md is reverse-chronological since 2026-05-12 (GH #3): newest entry first,
// so the most recent N are the FIRST N — take from the head, not the tail.
let recentLogHeadings = []
try {
  const logRaw = await readFile(join(WIKI_DIR, "log.md"), "utf8")
  const headings = logRaw
    .split("\n")
    .filter((line) => /^## \[\d{4}-\d{2}-\d{2}\] /.test(line))
  recentLogHeadings = headings.slice(0, RECENT_LOG_ENTRIES)
} catch {}

// Find the HIGHEST wiki schema marker (v0.x[.y]) mentioned anywhere in log.md.
// Restricted to the v0.* range so external product versions (e.g. "Microsoft
// Agent Framework v1.0") don't pollute the result. Independent of file
// ordering, so the reverse-chronological flip (GH #3) doesn't change what
// gets reported as the latest schema version.
let latestVersion = null
try {
  const logRaw = await readFile(join(WIKI_DIR, "log.md"), "utf8")
  const versionMatches = [...logRaw.matchAll(/\bv0\.(\d+)(?:\.(\d+))?\b/g)]
  let best = null
  for (const m of versionMatches) {
    const score = parseInt(m[1], 10) * 1_000
                + (m[2] ? parseInt(m[2], 10) : 0)
    if (!best || score > best.score) best = { score, str: m[0] }
  }
  if (best) latestVersion = best.str
} catch {}

const lines = []
lines.push("# Wiki session context (auto-loaded by SessionStart hook)")
lines.push("")
lines.push(
  `**Catalog:** ${counts.concepts ?? 0} concepts, ${counts.entities ?? 0} entities, ${counts.sources ?? 0} sources, ${counts.threads ?? 0} threads, ${counts.syntheses ?? 0} syntheses.`,
)
if (latestVersion) {
  lines.push(`**Latest schema version mentioned in log:** ${latestVersion}.`)
}
lines.push("")
lines.push("**Recent activity** (most recent at the top):")
lines.push("")
if (recentLogHeadings.length === 0) {
  lines.push("- _(log.md missing or empty)_")
} else {
  for (const h of recentLogHeadings) {
    lines.push(`- ${h.replace(/^## /, "")}`)
  }
}
lines.push("")
lines.push("**Lifecycle flags:**")
lines.push("")
lines.push(
  `- ${stale.length} page(s) marked \`status: stale\`${stale.length > 0 ? ":" : "."}`,
)
for (const s of stale) lines.push(`  - ${s}`)
lines.push(
  `- ${lowConfidence.length} page(s) with \`confidence < 0.5\`${lowConfidence.length > 0 ? ":" : "."}`,
)
for (const { rel, confidence } of lowConfidence) {
  lines.push(`  - ${rel} (confidence ${confidence.toFixed(2)})`)
}
lines.push(
  `- ${indexGapTotal} page(s) missing from \`wiki/index.md\`${indexGapTotal > 0 ? ":" : "."}`,
)
for (const { sectionName, missing } of indexGapDetail) {
  lines.push(`  - ${sectionName}: ${missing.length} (run \`node scripts/lint-index-completeness.mjs\` for the list)`)
}
lines.push("")
lines.push(
  "Refer to [`CLAUDE.md`](../CLAUDE.md) for the full schema, [`llm-wiki-v2-plan.md`](../llm-wiki-v2-plan.md) for the staged release plan, and the most recent log entries for what's in flight.",
)

console.log(lines.join("\n"))
