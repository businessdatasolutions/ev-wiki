#!/usr/bin/env node
// Read-only walker over wiki/sources/*.md and wiki/entities/*.md.
//
// Surfaces *dangling authors* per the convention in CLAUDE.md §Lifecycle
// "Author-entity promotion": a name appearing in `author:` on ≥2 source pages
// must have an entity page (matched against the entity's canonical filename or
// any entry in its `aliases:` frontmatter). Names appearing on only 1 source
// remain correctly deferred and are NOT reported.
//
// Output:
//   1. List of dangling authors with their occurrence counts and source pages.
//   2. Summary counts: total authors / single-source (deferred OK) /
//      multi-source-with-entity (correctly promoted) /
//      multi-source-without-entity (action needed).
//
// Never edits files. Run from repo root with:
//   node scripts/lint-dangling-authors.mjs
//
// Exits 1 when any dangling authors are found, 0 otherwise — usable as a
// CI / pre-commit check.

import { readdir, readFile } from "node:fs/promises"
import { join, relative, dirname, basename } from "node:path"
import { fileURLToPath } from "node:url"
import matter from "gray-matter"

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const SOURCES_DIR = join(REPO_ROOT, "wiki/sources")
const ENTITIES_DIR = join(REPO_ROOT, "wiki/entities")

async function listMarkdown(dir) {
  const entries = await readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    if (entry.isDirectory()) continue
    if (!entry.name.endsWith(".md")) continue
    files.push(join(dir, entry.name))
  }
  return files
}

function fold(name) {
  // Case-fold + collapse internal whitespace. Diacritics intentionally NOT
  // stripped — if a user's filesystem-canonical entity name strips diacritics
  // (precedent: "Jesper B. Sorensen.md" entity for "Jesper B. Sørensen"
  // author), the entity page should declare that surface form via aliases.
  return name.trim().replace(/\s+/g, " ").toLowerCase()
}

function authorList(value) {
  if (Array.isArray(value)) return value.filter((v) => typeof v === "string")
  if (typeof value === "string") return [value]
  return []
}

// 1. Walk sources, collect author → source-pages map.
const authorOccurrences = new Map() // foldedName -> { display, sources: [] }

for (const file of await listMarkdown(SOURCES_DIR)) {
  const raw = await readFile(file, "utf8")
  const { data } = matter(raw)
  const sourceRel = relative(REPO_ROOT, file)
  for (const authorName of authorList(data.author)) {
    const folded = fold(authorName)
    if (!folded) continue
    const entry = authorOccurrences.get(folded) ?? { display: authorName.trim(), sources: [] }
    entry.sources.push(sourceRel)
    authorOccurrences.set(folded, entry)
  }
}

// 2. Walk entities, collect canonical names + aliases, all folded.
const knownEntities = new Set()

for (const file of await listMarkdown(ENTITIES_DIR)) {
  const canonical = basename(file, ".md")
  knownEntities.add(fold(canonical))
  const raw = await readFile(file, "utf8")
  const { data } = matter(raw)
  if (Array.isArray(data.aliases)) {
    for (const alias of data.aliases) {
      if (typeof alias === "string") knownEntities.add(fold(alias))
    }
  }
}

// 3. Categorize.
const danglingMulti = []
const promotedMulti = []
const deferredSingle = []

for (const [folded, entry] of authorOccurrences) {
  const count = entry.sources.length
  const hasEntity = knownEntities.has(folded)
  if (count >= 2 && !hasEntity) {
    danglingMulti.push({ name: entry.display, count, sources: entry.sources })
  } else if (count >= 2 && hasEntity) {
    promotedMulti.push(entry.display)
  } else {
    deferredSingle.push(entry.display)
  }
}

danglingMulti.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))

// 4. Report.
console.log(`Dangling authors (≥2 source mentions, no entity page) — ${danglingMulti.length}`)
console.log("------------------------")
if (danglingMulti.length === 0) {
  console.log("  (none — all multi-source authors have entity pages)")
} else {
  for (const { name, count, sources } of danglingMulti) {
    console.log(`  ${name}  →  ${count} source mentions`)
    for (const s of sources) console.log(`      ${s}`)
  }
}
console.log()

console.log("Summary")
console.log("------------------------")
console.log(`  Total distinct authors in source frontmatter:   ${authorOccurrences.size}`)
console.log(`  Single-source (deferred, OK):                   ${deferredSingle.length}`)
console.log(`  Multi-source WITH entity page (OK):             ${promotedMulti.length}`)
console.log(`  Multi-source WITHOUT entity page (dangling):    ${danglingMulti.length}`)

process.exit(danglingMulti.length > 0 ? 1 : 0)
