#!/usr/bin/env node
// Walks all wiki/**/*.md, reads frontmatter, and emits wiki/.graph.json with
// node + edge lists derived from `type`, `kind`, `confidence`, and the v0.3
// `relationships:` block.
//
// Output schema:
//   {
//     "generated_at": "2026-05-05T08:30:00.000Z",
//     "node_count": N,
//     "edge_count": M,
//     "nodes": [
//       { "slug": "concepts/automation-vs-augmentation",
//         "type": "concept",
//         "kind": null,
//         "title": "Automation vs. Augmentation",
//         "confidence": 0.95,
//         "source_count": 10,
//         "last_confirmed": "2026-05-02" },
//       ...
//     ],
//     "edges": [
//       { "source": "concepts/foo",
//         "target": "entities/Bar",
//         "target_resolved": true,
//         "type": "authored-by",
//         "confidence": 0.7,
//         "via": "..." },
//       ...
//     ]
//   }
//
// Edges where the `target` slug doesn't resolve to an existing wiki page get
// `target_resolved: false` and `target` keeps the raw value — useful as a
// lint signal during the v0.3 migration.
//
// Run from repo root: node scripts/graph-export.mjs

import { readdir, readFile, writeFile } from "node:fs/promises"
import { join, relative, dirname, basename, extname } from "node:path"
import { fileURLToPath } from "node:url"
import matter from "gray-matter"

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const WIKI_DIR = join(REPO_ROOT, "wiki")
const OUTPUT = join(WIKI_DIR, ".graph.json")

// Recursively list all .md files under a directory.
async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...(await walk(full)))
    } else if (entry.name.endsWith(".md")) {
      files.push(full)
    }
  }
  return files
}

// Convert a file path to a slug: relative to wiki/, drop .md, dasherize spaces.
function fileToSlug(file) {
  const rel = relative(WIKI_DIR, file)
  const noExt = rel.slice(0, -extname(rel).length)
  return noExt.replace(/\s+/g, "-")
}

// Match a relationship target string (e.g. "Erik-Brynjolfsson" or
// "ai-employment-effects" or "entities/Erik-Brynjolfsson") against the node
// list. Returns the canonical slug if found, else null.
function resolveTarget(target, nodesBySlug, nodesByBasename) {
  const normalized = target.replace(/\s+/g, "-")
  if (nodesBySlug.has(normalized)) return normalized
  if (nodesByBasename.has(normalized)) return nodesByBasename.get(normalized)
  return null
}

const files = await walk(WIKI_DIR)
const nodes = []
const nodesBySlug = new Map()
const nodesByBasename = new Map()
const ambiguousBasenames = new Set()
// Edge classes per CLAUDE.md §Graph. DERIVED from the type — never read from a page's
// frontmatter. Four kinds of relationship: does the claim hold up (evidential), what led
// to what (causal), how does it decompose (structural), who stands behind it (provenance).
// An unknown type stamps `null` rather than guessing; lint-page.mjs catches the vocabulary
// violation separately.
const EDGE_CLASS = {
  supports: "evidential",
  contradicts: "evidential",
  supersedes: "evidential",
  caused: "causal",
  fixed: "causal",
  "part-of": "structural",
  "instance-of": "structural",
  "depends-on": "structural",
  uses: "structural",
  "authored-by": "provenance",
  "published-by": "provenance",
  employs: "provenance",
  // ev-wiki (2026-10-06): which models a tester puts side by side. Symmetric in
  // meaning; stored once, on the model page, and inverted here like any edge.
  "competes-with": "market",
}

const edges = []

// First pass: build node list
for (const file of files) {
  // Skip the index, log, and any dotfiles
  const base = basename(file)
  if (base === "index.md" || base === "log.md" || base.startsWith(".")) continue

  const raw = await readFile(file, "utf8")
  const { data } = matter(raw)
  const slug = fileToSlug(file)
  const node = {
    slug,
    type: typeof data.type === "string" ? data.type : null,
    kind: typeof data.kind === "string" ? data.kind : null,
    title: typeof data.title === "string" ? data.title : basename(file, ".md"),
    confidence: typeof data.confidence === "number" ? data.confidence : null,
    source_count: typeof data.source_count === "number" ? data.source_count : null,
    last_confirmed: typeof data.last_confirmed === "string" ? data.last_confirmed : null,
  }
  nodes.push(node)
  nodesBySlug.set(slug, node)

  const lastSegment = slug.split("/").pop() ?? slug
  if (nodesByBasename.has(lastSegment)) {
    ambiguousBasenames.add(lastSegment)
  } else {
    nodesByBasename.set(lastSegment, slug)
  }
}

// Drop ambiguous basenames from the basename index — relationships pointing
// at a bare name that resolves to multiple folders must be qualified with the
// folder prefix to disambiguate.
for (const ambiguous of ambiguousBasenames) {
  nodesByBasename.delete(ambiguous)
}

// Second pass: build edge list from relationships
let unresolved = 0
for (const file of files) {
  const base = basename(file)
  if (base === "index.md" || base === "log.md" || base.startsWith(".")) continue

  const raw = await readFile(file, "utf8")
  const { data } = matter(raw)
  const slug = fileToSlug(file)
  const rels = data.relationships
  if (!Array.isArray(rels)) continue

  for (const rel of rels) {
    if (!rel || typeof rel.type !== "string" || typeof rel.target !== "string") continue
    const targetSlug = resolveTarget(rel.target, nodesBySlug, nodesByBasename)
    const resolved = targetSlug !== null
    if (!resolved) unresolved++
    edges.push({
      source: slug,
      target: targetSlug ?? rel.target,
      target_resolved: resolved,
      type: rel.type,
      class: EDGE_CLASS[rel.type] ?? null,
      confidence: typeof rel.confidence === "number" ? rel.confidence : null,
      via: typeof rel.via === "string" ? rel.via : null,
    })
  }
}

const output = {
  generated_at: new Date().toISOString(),
  node_count: nodes.length,
  edge_count: edges.length,
  unresolved_edge_count: unresolved,
  ambiguous_basenames: Array.from(ambiguousBasenames).sort(),
  nodes: nodes.sort((a, b) => a.slug.localeCompare(b.slug)),
  edges: edges.sort((a, b) =>
    a.source.localeCompare(b.source) || a.target.localeCompare(b.target),
  ),
}

await writeFile(OUTPUT, JSON.stringify(output, null, 2) + "\n", "utf8")

console.log(`Graph exported to ${relative(REPO_ROOT, OUTPUT)}`)
console.log(`  Nodes: ${nodes.length}`)
console.log(`  Edges: ${edges.length}`)
if (unresolved > 0) {
  console.log(`  Unresolved targets: ${unresolved}`)
}
if (ambiguousBasenames.size > 0) {
  console.log(`  Ambiguous basenames (require folder-qualified targets):`)
  for (const a of ambiguousBasenames) console.log(`    - ${a}`)
}
