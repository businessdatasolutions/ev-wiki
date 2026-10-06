#!/usr/bin/env node
// Read-only walker over wiki/concepts/*.md and wiki/entities/*.md.
//
// Reports:
//   1. Distribution of `confidence` values across pages.
//   2. Pages missing any of the v0.2 lifecycle fields
//      (`confidence`, `last_confirmed`, `source_count`).
//   3. Pages with `last_confirmed` older than 30 days.
//   4. Pages marked `status: stale` and whether they have `superseded_by`.
//
// Never edits files. Run from repo root with: node scripts/lint-confidence.mjs

import { readdir, readFile } from "node:fs/promises"
import { join, relative, dirname } from "node:path"
import { fileURLToPath } from "node:url"
import matter from "gray-matter"

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const TARGETS = ["wiki/concepts", "wiki/entities", "wiki/syntheses"]
const STALE_THRESHOLD_DAYS = 30

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

function bucket(confidence) {
  if (typeof confidence !== "number") return "missing"
  if (confidence < 0.5) return "<0.5"
  if (confidence < 0.7) return "0.5–0.7"
  if (confidence < 0.85) return "0.7–0.85"
  if (confidence <= 1.0) return "0.85–1.0"
  return "out-of-range"
}

function daysSince(dateStr) {
  if (typeof dateStr !== "string") return null
  const parsed = new Date(dateStr)
  if (isNaN(parsed.getTime())) return null
  const ms = Date.now() - parsed.getTime()
  return Math.floor(ms / 86400000)
}

const distribution = {
  missing: 0,
  "<0.5": 0,
  "0.5–0.7": 0,
  "0.7–0.85": 0,
  "0.85–1.0": 0,
  "out-of-range": 0,
}
const missingFields = []
const stalenessFlags = []
const superseded = []

for (const target of TARGETS) {
  const dir = join(REPO_ROOT, target)
  const files = await listMarkdown(dir)
  for (const file of files) {
    const raw = await readFile(file, "utf8")
    const { data } = matter(raw)
    const rel = relative(REPO_ROOT, file)

    distribution[bucket(data.confidence)]++

    const missing = []
    if (typeof data.confidence !== "number") missing.push("confidence")
    if (typeof data.last_confirmed !== "string") missing.push("last_confirmed")
    if (typeof data.source_count !== "number") missing.push("source_count")
    if (missing.length > 0) missingFields.push({ rel, missing })

    const days = daysSince(data.last_confirmed)
    if (days !== null && days > STALE_THRESHOLD_DAYS) {
      stalenessFlags.push({ rel, days })
    }

    if (typeof data.status === "string" && data.status.toLowerCase() === "stale") {
      superseded.push({ rel, superseded_by: data.superseded_by })
    }
  }
}

console.log("Confidence distribution")
console.log("------------------------")
for (const [k, v] of Object.entries(distribution)) {
  console.log(`  ${k.padEnd(12)} ${v}`)
}
console.log()

console.log(`Pages missing v0.2 lifecycle fields (${missingFields.length})`)
console.log("------------------------")
for (const { rel, missing } of missingFields) {
  console.log(`  ${rel}  →  missing: ${missing.join(", ")}`)
}
console.log()

console.log(`Pages with last_confirmed > ${STALE_THRESHOLD_DAYS} days old (${stalenessFlags.length})`)
console.log("------------------------")
for (const { rel, days } of stalenessFlags) {
  console.log(`  ${rel}  →  ${days} days`)
}
console.log()

console.log(`Pages marked status: stale (${superseded.length})`)
console.log("------------------------")
for (const { rel, superseded_by } of superseded) {
  const target = superseded_by ?? "(no superseded_by set)"
  console.log(`  ${rel}  →  ${target}`)
}

const exitCode = missingFields.length > 0 ? 1 : 0
process.exit(exitCode)
