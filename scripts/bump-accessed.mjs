#!/usr/bin/env node
// v0.5 quality slice — procedural helper to bump `accessed_at` after a
// query-time page read. Used in lieu of full MCP integration (which would
// auto-bump as part of `qmd_query` semantics).
//
// Per CLAUDE.md §Retention, `accessed_at` is the reinforcement signal that
// resets the decay curve. Every time a page is read into context to answer
// a query, that page's `accessed_at` should be bumped to today.
//
// Usage:
//   node scripts/bump-accessed.mjs <slug-or-path> [<slug-or-path> ...]
//   node scripts/bump-accessed.mjs --dry-run <slug>
//
// Slugs are resolved against wiki/concepts/, wiki/entities/, and wiki/syntheses/.
// Paths (containing `/` or `.md`) are taken as-is relative to the repo root.
//
// Sources do not carry `accessed_at` — passing a source slug is an error.

import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, basename, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');
const DRY_RUN = process.argv.includes('--dry-run');
const args = process.argv.slice(2).filter((a) => a !== '--dry-run');

if (args.length === 0) {
  console.error('usage: node scripts/bump-accessed.mjs [--dry-run] <slug> [<slug> ...]');
  process.exit(1);
}

const SEARCH_DIRS = ['wiki/concepts', 'wiki/entities', 'wiki/syntheses'];

function resolveTarget(input) {
  // Path-like (contains / or .md)
  if (input.includes('/') || input.endsWith('.md')) {
    const p = input.startsWith('/') ? input : join(REPO_ROOT, input);
    return existsSync(p) ? p : null;
  }
  // Slug — try each searchable dir
  for (const d of SEARCH_DIRS) {
    const candidate = join(REPO_ROOT, d, input + '.md');
    if (existsSync(candidate)) return candidate;
    // Try unsluggified (spaces) for entities like "Erik Brynjolfsson"
    const unsluggified = join(REPO_ROOT, d, input.replace(/-/g, ' ') + '.md');
    if (existsSync(unsluggified)) return unsluggified;
  }
  // Last-ditch: walk dirs and match basename
  for (const d of SEARCH_DIRS) {
    const full = join(REPO_ROOT, d);
    try {
      for (const name of readdirSync(full)) {
        const stem = basename(name, '.md');
        if (
          stem === input ||
          stem.replace(/\s+/g, '-') === input ||
          stem.toLowerCase() === input.toLowerCase()
        ) {
          return join(full, name);
        }
      }
    } catch {}
  }
  return null;
}

function bumpFile(file, today) {
  // Source pages are forbidden
  if (file.includes('/sources/')) {
    return { ok: false, reason: "sources don't carry accessed_at" };
  }
  const content = readFileSync(file, 'utf8');
  if (!content.startsWith('---\n')) return { ok: false, reason: 'no frontmatter' };
  const fmEnd = content.indexOf('\n---\n', 4);
  if (fmEnd === -1) return { ok: false, reason: 'unterminated frontmatter' };

  const fm = content.slice(4, fmEnd);
  const lcMatch = fm.match(/^last_confirmed:[ \t]*(.+)$/m);
  // Mirror the quote style of last_confirmed if present, otherwise quote.
  const quotedToday = lcMatch && /^"/.test(lcMatch[1]) ? `"${today}"` : `"${today}"`;

  const accessedMatch = fm.match(/^accessed_at:[ \t]*(.+)$/m);
  if (accessedMatch) {
    const current = accessedMatch[1].trim().replace(/^["']|["']$/g, '');
    if (current === today) return { ok: true, noop: true };
    const newFm = fm.replace(
      /^accessed_at:[ \t]*.+$/m,
      `accessed_at: ${quotedToday}`,
    );
    const newContent = '---\n' + newFm + content.slice(fmEnd);
    if (!DRY_RUN) writeFileSync(file, newContent);
    return { ok: true, oldValue: current };
  } else {
    // Insert after last_confirmed if present, else after a known anchor
    if (lcMatch) {
      const newFm = fm.replace(
        /^(last_confirmed:[ \t]*.+)$/m,
        `$1\naccessed_at: ${quotedToday}`,
      );
      const newContent = '---\n' + newFm + content.slice(fmEnd);
      if (!DRY_RUN) writeFileSync(file, newContent);
      return { ok: true, inserted: true };
    }
    return { ok: false, reason: 'no last_confirmed to anchor after' };
  }
}

const today = new Date().toISOString().slice(0, 10);
console.log(`${DRY_RUN ? '[DRY-RUN] ' : ''}Bumping accessed_at to ${today}`);

let bumped = 0;
let noop = 0;
let failed = 0;

for (const arg of args) {
  const file = resolveTarget(arg);
  if (!file) {
    console.log(`  ✗ ${arg} — page not found`);
    failed++;
    continue;
  }
  const rel = file.slice(REPO_ROOT.length + 1);
  const r = bumpFile(file, today);
  if (!r.ok) {
    console.log(`  ✗ ${rel} — ${r.reason}`);
    failed++;
  } else if (r.noop) {
    console.log(`  · ${rel} (already at ${today})`);
    noop++;
  } else if (r.inserted) {
    console.log(`  + ${rel} (inserted ${today})`);
    bumped++;
  } else {
    console.log(`  ✓ ${rel} (${r.oldValue} → ${today})`);
    bumped++;
  }
}

console.log(`\nSummary: ${bumped} bumped, ${noop} already-current, ${failed} failed.`);
process.exit(failed > 0 ? 1 : 0);
