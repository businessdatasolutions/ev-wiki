#!/usr/bin/env node
// Read-only walker over wiki/{sources,entities,concepts,syntheses,threads}/*.md
// vs. the corresponding section of wiki/index.md.
//
// Surfaces *uncatalogued pages*: a page that exists on disk but has no
// matching `- [[target]]` bullet in its section of index.md. This is the
// failure mode discovered 2026-07-04 (GH: 28 entity pages existed but were
// never added to the Entities section — each ingest wrote the entity's own
// page and mentioned it inline in a Sources-section paragraph, but skipped
// the required standalone index bullet, silently, across ~28 sessions).
//
// Matches folder-qualified bullets too (e.g. `concepts/foo|foo`, used when a
// basename collides across sections) by stripping the directory prefix
// before comparing to the on-disk basename.
//
// Never edits files. Run from repo root with:
//   node scripts/lint-index-completeness.mjs
//
// Exits 1 when any page is uncatalogued, 0 otherwise — usable as a
// CI / pre-commit check, and as the SessionStart hook's data source.

import { readdir, readFile } from "node:fs/promises"
import { join, dirname, basename, relative } from "node:path"
import { fileURLToPath } from "node:url"

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const WIKI_DIR = join(REPO_ROOT, "wiki")
const INDEX_PATH = join(WIKI_DIR, "index.md")

// Section header text -> wiki subdirectory name.
const SECTIONS = {
  // ev-wiki schrijft de index in het Nederlands.
  Bronnen: "sources",
  Entiteiten: "entities",
  Concepten: "concepts",
  Syntheses: "syntheses",
  Threads: "threads",
}

async function listBasenames(dir) {
  try {
    const entries = await readdir(dir, { withFileTypes: true })
    return entries
      .filter((e) => e.isFile() && e.name.endsWith(".md") && !e.name.startsWith("."))
      .map((e) => basename(e.name, ".md"))
  } catch {
    return []
  }
}

function parseIndexSections(raw) {
  const lines = raw.split("\n")
  const headerLineIdx = {}
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^## (\w+)$/)
    if (m && m[1] in SECTIONS) headerLineIdx[m[1]] = i
  }
  const order = Object.keys(SECTIONS).filter((name) => name in headerLineIdx)
  const sectionEntries = {}
  for (let idx = 0; idx < order.length; idx++) {
    const name = order[idx]
    const start = headerLineIdx[name]
    const end = idx + 1 < order.length ? headerLineIdx[order[idx + 1]] : lines.length
    const body = lines.slice(start + 1, end)
    const targets = new Set()
    for (const line of body) {
      const m = line.match(/^- \[\[([^\]]+)\]\]/)
      if (!m) continue
      let inner = m[1]
      if (inner.includes("|")) inner = inner.split("|")[0]
      // Strip a leading "sources/" / "entities/" / "concepts/" / "syntheses/" /
      // "threads/" qualifier used to disambiguate colliding basenames.
      const stripped = inner.replace(/^(sources|entities|concepts|syntheses|threads)\//, "")
      targets.add(stripped)
    }
    sectionEntries[name] = targets
  }
  return sectionEntries
}

// Exported so other scripts (e.g. session-start.mjs) can reuse the check
// without shelling out or duplicating the parsing logic.
export async function checkIndexCompleteness() {
  const indexRaw = await readFile(INDEX_PATH, "utf8")
  const indexed = parseIndexSections(indexRaw)

  let totalMissing = 0
  const report = []

  for (const [sectionName, subdir] of Object.entries(SECTIONS)) {
    const onDisk = await listBasenames(join(WIKI_DIR, subdir))
    const listed = indexed[sectionName] ?? new Set()
    const missing = onDisk.filter((name) => !listed.has(name)).sort((a, b) => a.localeCompare(b))
    report.push({ sectionName, subdir, onDiskCount: onDisk.length, listedCount: listed.size, missing })
    totalMissing += missing.length
  }

  return { report, totalMissing }
}

// Only run as a CLI report when invoked directly (not when imported).
const isMain = process.argv[1] && import.meta.url === `file://${process.argv[1]}`
if (isMain) {
  const { report, totalMissing } = await checkIndexCompleteness()

  console.log(`Uncatalogued pages (exist on disk, no index.md bullet) — ${totalMissing}`)
  console.log("------------------------")
  if (totalMissing === 0) {
    console.log("  (none — every page on disk is catalogued)")
  } else {
    for (const { sectionName, subdir, missing } of report) {
      if (missing.length === 0) continue
      console.log(`  ## ${sectionName} (wiki/${subdir}/) — ${missing.length} missing:`)
      for (const name of missing) console.log(`      ${name}`)
    }
  }
  console.log()

  console.log("Summary")
  console.log("------------------------")
  for (const { sectionName, subdir, onDiskCount, listedCount, missing } of report) {
    console.log(
      `  ${sectionName.padEnd(10)} wiki/${subdir}/: ${onDiskCount} on disk, ${listedCount} indexed, ${missing.length} missing`,
    )
  }

  process.exit(totalMissing > 0 ? 1 : 0)
}
