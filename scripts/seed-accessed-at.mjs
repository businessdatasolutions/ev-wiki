#!/usr/bin/env node
// v0.5 retention slice — seed accessed_at on concept and entity pages.
//
// Idempotent: skips pages where accessed_at: is already present.
// Deterministic: accessed_at := last_confirmed (verbatim, including quote style).
// Scope: wiki/concepts/**/*.md, wiki/entities/**/*.md, wiki/syntheses/**/*.md.
//   - Sources don't decay (no accessed_at, per §Retention).
//   - Threads are provisional and don't carry the full lifecycle contract.
//   - Syntheses added after the v0.5 quality scorer flagged the omission.
//
// Run: node scripts/seed-accessed-at.mjs [--dry-run]
// Re-run safe.

import { readFileSync, writeFileSync } from 'node:fs';
import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');
const TARGETS = ['wiki/concepts', 'wiki/entities', 'wiki/syntheses'];
const DRY_RUN = process.argv.includes('--dry-run');

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (name.endsWith('.md')) out.push(p);
  }
  return out;
}

const stats = { scanned: 0, seeded: 0, alreadyPresent: 0, noLastConfirmed: 0, noFrontmatter: 0 };
const seededFiles = [];

for (const rel of TARGETS) {
  const dir = join(REPO_ROOT, rel);
  for (const file of walk(dir)) {
    stats.scanned++;
    const text = readFileSync(file, 'utf8');

    // Frontmatter must start at byte 0 with ---
    if (!text.startsWith('---\n')) { stats.noFrontmatter++; continue; }
    const fmEnd = text.indexOf('\n---\n', 4);
    if (fmEnd === -1) { stats.noFrontmatter++; continue; }
    const frontmatter = text.slice(4, fmEnd);

    if (/^accessed_at:/m.test(frontmatter)) { stats.alreadyPresent++; continue; }

    const lcMatch = frontmatter.match(/^last_confirmed:[ \t]*(.+)$/m);
    if (!lcMatch) { stats.noLastConfirmed++; continue; }
    const lcValue = lcMatch[1];

    const newFrontmatter = frontmatter.replace(
      /^(last_confirmed:[ \t]*.+)$/m,
      `$1\naccessed_at: ${lcValue}`
    );
    const newText = '---\n' + newFrontmatter + text.slice(4 + frontmatter.length);

    if (!DRY_RUN) writeFileSync(file, newText, 'utf8');
    stats.seeded++;
    seededFiles.push(file.slice(REPO_ROOT.length + 1));
  }
}

console.log(`${DRY_RUN ? '[DRY-RUN] ' : ''}seed-accessed-at.mjs results:`);
console.log(`  scanned:          ${stats.scanned}`);
console.log(`  seeded:           ${stats.seeded}`);
console.log(`  already present:  ${stats.alreadyPresent}`);
console.log(`  no last_confirmed:${stats.noLastConfirmed}`);
console.log(`  no frontmatter:   ${stats.noFrontmatter}`);

if (seededFiles.length > 0 && seededFiles.length <= 20) {
  console.log('\nSeeded files:');
  for (const f of seededFiles) console.log(`  ${f}`);
} else if (seededFiles.length > 20) {
  console.log(`\nFirst 10 of ${seededFiles.length} seeded files:`);
  for (const f of seededFiles.slice(0, 10)) console.log(`  ${f}`);
  console.log(`  ... and ${seededFiles.length - 10} more`);
}
