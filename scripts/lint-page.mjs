#!/usr/bin/env node
// Fired on PostToolUse hook (configured in .claude/settings.json) for Edit
// and Write tool calls whose target path is under wiki/. Validates the v0.2
// lifecycle contract and the v0.3 body-wikilink rule on the file that was
// just edited. Outputs warnings to stderr; never blocks (always exits 0).
//
// Hook input (stdin, JSON):
//   { "tool_name": "Edit" | "Write",
//     "tool_input": { "file_path": "/abs/path/to/file.md", ... } }
//
// Read-only against wiki content. Per CLAUDE.md §Hooks, hooks must not edit
// any wiki/**/*.md page; this script reads the edited file, surfaces issues
// for Claude/the user to address, and exits.

import { readFile } from "node:fs/promises"
import { resolve, relative, basename, sep } from "node:path"
import matter from "gray-matter"

const REPO_ROOT = resolve(new URL(".", import.meta.url).pathname, "..")
const WIKI_PREFIX = `wiki${sep}`
const LIFECYCLE_TYPES = new Set(["concept", "entity", "synthesis"])

// Read JSON input from stdin (hook payload). If we can't parse it, skip the
// lint silently rather than blocking the tool call.
async function readStdin() {
  let raw = ""
  for await (const chunk of process.stdin) raw += chunk
  return raw.trim()
}

let payload = null
try {
  const raw = await readStdin()
  if (raw) payload = JSON.parse(raw)
} catch {
  // Malformed payload — exit silently so we never block tool calls on hook bugs
  process.exit(0)
}

const filePath = payload?.tool_input?.file_path
if (typeof filePath !== "string" || !filePath.endsWith(".md")) process.exit(0)

const absPath = resolve(filePath)
const rel = relative(REPO_ROOT, absPath)
if (!rel.startsWith(WIKI_PREFIX)) process.exit(0)
// Skip the catalog files — they have a different shape from page files.
if (rel === `wiki${sep}index.md` || rel === `wiki${sep}log.md`) process.exit(0)

let raw
try {
  raw = await readFile(absPath, "utf8")
} catch {
  // File doesn't exist (e.g. an Edit that's about to fail) — let the tool's
  // own error handle it.
  process.exit(0)
}

let parsed
try {
  parsed = matter(raw)
} catch (e) {
  process.stderr.write(`lint-page: ${rel}: frontmatter parse error: ${e.message}\n`)
  process.exit(0)
}

const fm = parsed.data ?? {}
const body = parsed.content ?? ""
const warnings = []

// 1. Frontmatter contract (v0.2 §Lifecycle): concepts/entities/syntheses must
//    carry confidence, last_confirmed, source_count.
if (typeof fm.type === "string" && LIFECYCLE_TYPES.has(fm.type)) {
  if (typeof fm.confidence !== "number") warnings.push("missing `confidence` (v0.2 §Lifecycle)")
  if (typeof fm.last_confirmed !== "string")
    warnings.push("missing `last_confirmed` (v0.2 §Lifecycle)")
  if (typeof fm.source_count !== "number")
    warnings.push("missing `source_count` (v0.2 §Lifecycle)")
}

// 2. Confidence range
if (typeof fm.confidence === "number") {
  if (fm.confidence < 0 || fm.confidence > 1) {
    warnings.push(`confidence ${fm.confidence} outside [0, 1]`)
  } else if (fm.confidence === 0) {
    warnings.push("confidence is 0 (v0.2 §Lifecycle: never use 0 as a default; pick a defensible value)")
  }
}

// 3. Confidence vs source_count consistency (v0.2 §Lifecycle Confidence rules):
//    0.70 baseline + 0.05 per additional source + 0.05 peer-reviewed bonus,
//    cap 0.95. The defensible generous max simplifies to
//      min(0.95, 0.70 + 0.05 * source_count)
//    We warn when declared confidence exceeds this max (small tolerance avoids
//    floating-point quirks). We do NOT warn on values BELOW the range — being
//    more conservative than the math is legitimate (unflagged contradictions,
//    judgment-call dampening, vendor-/anecdotal-source cap at 0.75 applied
//    without explicit frontmatter flag). Inspired by Mysore 2026's "Context
//    Debt" vocabulary — the lint that names claims-beyond-evidence.
if (
  typeof fm.confidence === "number" &&
  typeof fm.source_count === "number" &&
  fm.source_count > 0
) {
  const defensibleMax = Math.min(0.95, 0.70 + 0.05 * fm.source_count)
  const TOLERANCE = 0.01
  if (fm.confidence > defensibleMax + TOLERANCE) {
    warnings.push(
      `confidence ${fm.confidence} > defensible max ${defensibleMax.toFixed(2)} for source_count ${fm.source_count} (v0.2 §Lifecycle Confidence rules: 0.70 baseline + 0.05 per additional source + 0.05 peer-reviewed bonus, cap 0.95). Either add a source or lower confidence. Note: vendor-/anecdotal sources are capped at 0.75 regardless of count.`,
    )
  }
}

// 4. last_confirmed must be an ISO date string (v0.2 used quoted YAML strings)
if (fm.last_confirmed !== undefined && typeof fm.last_confirmed !== "string") {
  warnings.push(
    "last_confirmed must be a quoted YAML string like \"2026-05-05\", not a bare date (gray-matter parses bare dates as Date objects)",
  )
}

// 5. v0.3 body-wikilink rule: every relationship target must appear as a body
//    wikilink. Match `[[target]]` or `[[target|...]]` or `[[folder/target]]`
//    and `[[folder/target|...]]`. Compare on simplified slug (basename only,
//    spaces normalized to dashes).
if (Array.isArray(fm.relationships) && fm.relationships.length > 0) {
  const wikilinkRe = /\[\[([^\]|]+)(?:\|[^\]]*)?\]\]/g
  const presentSlugs = new Set()
  for (const m of body.matchAll(wikilinkRe)) {
    const linkTarget = m[1].trim()
    presentSlugs.add(linkTarget)
    presentSlugs.add(linkTarget.split("/").pop())
    presentSlugs.add(linkTarget.replace(/\s+/g, "-"))
  }
  for (const rel of fm.relationships) {
    if (!rel || typeof rel.target !== "string") continue
    const target = rel.target.trim()
    const targetBasename = target.split("/").pop()
    const targetNormalized = target.replace(/\s+/g, "-")
    const found =
      presentSlugs.has(target) ||
      presentSlugs.has(targetBasename) ||
      presentSlugs.has(targetNormalized)
    if (!found) {
      warnings.push(
        `relationships.${rel.type ?? "?"} target \`${target}\` has no matching [[wikilink]] in body (v0.3 §Graph body-wikilink rule)`,
      )
    }
  }
}

// 6. Closed relationship vocabulary (v0.3 §Graph)
const RELATIONSHIP_VOCAB = new Set([
  "competes-with",
  "supports",
  "contradicts",
  "caused",
  "fixed",
  "supersedes",
  "uses",
  "depends-on",
  "part-of",
  "instance-of",
  "authored-by",
  "published-by",
  "employs",
])
if (Array.isArray(fm.relationships)) {
  for (const r of fm.relationships) {
    if (!r || typeof r.type !== "string") continue
    if (!RELATIONSHIP_VOCAB.has(r.type)) {
      warnings.push(
        `relationships type \`${r.type}\` is outside the closed vocabulary (v0.3 §Graph)`,
      )
    }
  }
}

// 7. Stale-page protocol (v0.2 §Lifecycle): a page with `status: stale` must
//    have `superseded_by`.
if (typeof fm.status === "string" && fm.status.toLowerCase() === "stale") {
  if (!fm.superseded_by) {
    warnings.push(
      "status: stale but no `superseded_by` set (v0.2 §Lifecycle supersession protocol)",
    )
  }
}

// 8. EV-lens op bronpagina's (CLAUDE.md §EV-lens). Drie velden:
//    - `feitsoorten:` uit een gesloten lijst. De enige bron van die lijst is
//      wiki/concepts/feitsoorten.md; houd deze Set daarmee gelijk.
//      Lichaamstweeling: elke feitsoort komt als woord in de tekst terug.
//    - `merken:` en `modellen:` slugs van merk- en modelpagina's; elk staat als
//      [[wikilink]] in de tekst, en het merk van elk model staat in `merken:`.
//    - `weergaven:` metingen {datum, aantal}; verplicht op een YouTube-bron,
//      want een aantal zonder dag is met geen ander aantal te vergelijken.
const FEITSOORTEN = new Set(["fabrieksopgave", "meting", "valkuil", "oordeel", "merk-en-service"])

if (fm.type === "source") {
  const bodyLower = body.toLowerCase()
  const wbRe = (s) =>
    new RegExp(`(?<![A-Za-z0-9_-])${s.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}(?![A-Za-z0-9_-])`, "i")
  if (Array.isArray(fm.feitsoorten)) {
    for (const tag of fm.feitsoorten) {
      const slug = String(tag).trim()
      if (!FEITSOORTEN.has(slug)) {
        warnings.push(
          `feitsoort \`${slug}\` staat niet in de gesloten lijst (wiki/concepts/feitsoorten.md; CLAUDE.md §EV-lens)`,
        )
      } else if (!new RegExp(`(?<![a-z0-9])${slug.split("-").join("[- ]")}(?:en|n|s)?(?![a-z0-9])`, "i").test(bodyLower)) {
        // "Fabrieksopgaven" en "Merk en service" tellen als `fabrieksopgave` en `merk-en-service`.
        warnings.push(
          `feitsoort \`${slug}\` komt niet in de tekst terug (CLAUDE.md §EV-lens, lichaamstweeling: noem de soort in de tekst)`,
        )
      }
    }
  }
  const linkRe = (slug) =>
    new RegExp(`\\[\\[(?:entities/)?${slug.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:[|#\\]])`, "i")
  for (const veld of ["merken", "modellen"]) {
    if (!Array.isArray(fm[veld])) continue
    for (const m of fm[veld]) {
      const slug = String(m).trim()
      if (!linkRe(slug).test(body)) {
        warnings.push(`\`${slug}\` staat in \`${veld}:\` maar niet als [[wikilink]] in de tekst (CLAUDE.md §EV-lens)`)
      }
    }
  }
  if (Array.isArray(fm.modellen)) {
    const merken = new Set((Array.isArray(fm.merken) ? fm.merken : []).map((x) => String(x).trim()))
    for (const m of fm.modellen) {
      const slug = String(m).trim()
      let merk = null
      try {
        merk = matter(await readFile(resolve(REPO_ROOT, "wiki", "entities", `${slug}.md`), "utf8")).data.merk
      } catch {
        warnings.push(`model \`${slug}\` heeft geen pagina in wiki/entities/ (CLAUDE.md §EV-lens)`)
        continue
      }
      if (merk && !merken.has(String(merk).trim())) {
        warnings.push(`model \`${slug}\` is van merk \`${merk}\`, maar dat staat niet in \`merken:\` (CLAUDE.md §EV-lens)`)
      }
    }
  }
  // `concurrenten:` (CLAUDE.md §Concurrentie): wat een tester naast elkaar zet.
  // Elk model en elke tegenhanger heeft een modelpagina, en de bewering heeft
  // een tijdstempel, anders is hij in de video niet terug te vinden.
  if (Array.isArray(fm.concurrenten)) {
    for (const c of fm.concurrenten) {
      const slugs = [c?.model, ...(Array.isArray(c?.tegen) ? c.tegen : [])].filter(Boolean).map((x) => String(x).trim())
      if (!c?.model || !Array.isArray(c?.tegen) || c.tegen.length === 0) {
        warnings.push(`concurrenten-regel \`${JSON.stringify(c)}\` mist \`model\` of \`tegen\` (CLAUDE.md §Concurrentie)`)
      }
      if (fm.kind === "video" && !c?.tijd) {
        warnings.push(`concurrenten-regel voor \`${c?.model}\` heeft geen \`tijd\` (tijdstempel in de video)`)
      }
      for (const slug of slugs) {
        try {
          await readFile(resolve(REPO_ROOT, "wiki", "entities", `${slug}.md`), "utf8")
        } catch {
          warnings.push(`concurrent \`${slug}\` heeft geen modelpagina in wiki/entities/ (CLAUDE.md §Concurrentie)`)
        }
      }
    }
  }
  // `vergelijking: true` (CLAUDE.md §Concurrentie): elk paar modellen van verschillende
  // merken in `modellen:` is concurrentie en staat dus in `concurrenten:`, in een van
  // beide richtingen. Het merk komt uit de modelpagina.
  if (fm.vergelijking === true && Array.isArray(fm.modellen) && fm.modellen.length > 1) {
    const merkVan = {}
    for (const m of fm.modellen) {
      try {
        merkVan[m] = matter(await readFile(resolve(REPO_ROOT, "wiki", "entities", `${m}.md`), "utf8")).data.merk
      } catch {}
    }
    const paren = new Set()
    for (const c of Array.isArray(fm.concurrenten) ? fm.concurrenten : []) {
      for (const t of Array.isArray(c?.tegen) ? c.tegen : []) {
        paren.add(`${c.model}|${t}`)
        paren.add(`${t}|${c.model}`)
      }
    }
    for (let i = 0; i < fm.modellen.length; i++) {
      for (let j = i + 1; j < fm.modellen.length; j++) {
        const [a, b] = [fm.modellen[i], fm.modellen[j]]
        if (merkVan[a] && merkVan[b] && merkVan[a] !== merkVan[b] && !paren.has(`${a}|${b}`)) {
          warnings.push(`vergelijking: \`${a}\` en \`${b}\` (verschillende merken) staan niet als paar in \`concurrenten:\` (CLAUDE.md §Concurrentie)`)
        }
      }
    }
  }
  const isYoutube = typeof fm.url === "string" && /youtube\.com|youtu\.be/.test(fm.url)
  if (isYoutube && !Array.isArray(fm.weergaven)) {
    warnings.push("YouTube-bron zonder `weergaven:` (CLAUDE.md §EV-lens: aantal met peildatum)")
  }
  if (Array.isArray(fm.weergaven)) {
    for (const w of fm.weergaven) {
      const datum = w && w.datum instanceof Date ? w.datum.toISOString().slice(0, 10) : String(w?.datum ?? "")
      if (!/^\d{4}-\d{2}-\d{2}$/.test(datum) || !Number.isInteger(w?.aantal)) {
        warnings.push(`weergaven-meting \`${JSON.stringify(w)}\` heeft geen ISO-\`datum\` en geheel \`aantal\``)
      }
    }
  }
}

// 6. Source filename date prefix must match `date_published` (added 2026-09-16).
//    The prefix is load-bearing: it orders the index and is how every other page
//    cites the source, and nothing else checked it. A prefix copied from a
//    neighbouring page during a batch ingest is silent and survives review.
//
//    Two deliberate exemptions:
//    a) Prefixes on or before CONVENTION_CUTOFF. The first ~25 sources were
//       prefixed with their INGEST date, not their publish date; the
//       publish-date rule settled on 2026-05-08 and every source from that day
//       on matches. Renaming the legacy tier would break inbound wikilinks
//       across the corpus for no benefit, so they are grandfathered here rather
//       than silently ignored. Audited 2026-09-16: 25 legacy mismatches, zero
//       after the cutoff.
//    b) Partial `date_published` values (`2025`, `2025-11`) — legitimate for a
//       journal issue or an undated report, and nothing to compare against.
const CONVENTION_CUTOFF = "2026-05-08"
if (fm.type === "source") {
  const base = rel.slice(rel.lastIndexOf(sep) + 1)
  const m = base.match(/^(\d{4}-\d{2}-\d{2})-/)
  if (m && m[1] >= CONVENTION_CUTOFF && fm.date_published != null) {
    // gray-matter yields a Date for a full ISO date and a string for a partial one.
    const published =
      fm.date_published instanceof Date
        ? fm.date_published.toISOString().slice(0, 10)
        : String(fm.date_published).trim()
    if (/^\d{4}-\d{2}-\d{2}$/.test(published) && published !== m[1]) {
      warnings.push(
        `filename date prefix \`${m[1]}\` does not match \`date_published: ${published}\` ` +
          `(the prefix must be the publish date — rename the file, or fix the frontmatter if the prefix is right)`,
      )
    }
  }
}

if (warnings.length > 0) {
  process.stderr.write(`lint-page: ${rel}\n`)
  for (const w of warnings) process.stderr.write(`  - ${w}\n`)
}

process.exit(0)
