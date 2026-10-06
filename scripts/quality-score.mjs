#!/usr/bin/env node
// v0.5 quality slice — mechanical quality scoring for concepts and syntheses.
//
// Rubric (per CLAUDE.md §Quality):
//   - Structure   (0.40 weight): H1, required sections, frontmatter contract,
//                                body length ≥200 words, no empty sections,
//                                ≥3 outgoing wikilinks.
//   - Citations   (0.30 weight): source-page wikilinks per 1000 body words.
//                                Target: ≥3.0 per 1000 words.
//   - Consistency (0.30 weight): relationship targets exist, body-wikilink
//                                rule (v0.3), no broken wikilinks, debates
//                                section present when source_count > 1.
//
// Idempotent: only writes when score or notes changed. Quote style of other
// frontmatter fields is preserved (minimal-invasive regex replace).
//
// Usage:
//   node scripts/quality-score.mjs                # score all + write
//   node scripts/quality-score.mjs --dry-run      # score all, no write
//   node scripts/quality-score.mjs --page <slug>  # score single page

import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import { join, basename, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import matter from 'gray-matter';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');
const DRY_RUN = process.argv.includes('--dry-run');
const pageArgIdx = process.argv.indexOf('--page');
const PAGE_ARG = pageArgIdx >= 0 ? process.argv[pageArgIdx + 1] : null;

const TARGET_DIRS = ['wiki/concepts', 'wiki/syntheses'];
const KNOWN_SLUG_DIRS = ['wiki/concepts', 'wiki/entities', 'wiki/sources', 'wiki/syntheses', 'wiki/threads'];

function walk(dir) {
  const out = [];
  try {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) out.push(...walk(p));
      else if (name.endsWith('.md')) out.push(p);
    }
  } catch {}
  return out;
}

// Build known-slug set across all wiki/ subdirs (for cross-consistency checks).
// Includes filename slug, basename-normalised, and frontmatter aliases.
const knownSlugs = new Set();
for (const d of KNOWN_SLUG_DIRS) {
  for (const f of walk(join(REPO_ROOT, d))) {
    const slug = basename(f, '.md');
    knownSlugs.add(slug);
    knownSlugs.add(slug.replace(/\s+/g, '-'));
    knownSlugs.add(slug.replace(/\s+/g, '-').toLowerCase());
    // Aliases
    try {
      const raw = readFileSync(f, 'utf8');
      const fm = matter(raw).data;
      if (Array.isArray(fm.aliases)) {
        for (const a of fm.aliases) {
          if (typeof a === 'string') {
            knownSlugs.add(a);
            knownSlugs.add(a.replace(/\s+/g, '-'));
            knownSlugs.add(a.replace(/\s+/g, '-').toLowerCase());
          }
        }
      }
    } catch {}
  }
}

const WIKILINK_RE = /\[\[([^\]|]+)(?:\|[^\]]*)?\]\]/g;
const SOURCE_SLUG_RE = /^\d{4}-\d{2}-\d{2}-/;

// Wikilinks inside markdown tables escape the pipe: `[[slug\|alias]]`. The
// regex captures the slug including the trailing backslash. Strip it.
function normTarget(s) {
  return s.trim().replace(/\\+$/, '');
}
const SYNTHESIS_SECTIONS = [
  // ev-wiki: Dutch section names (CLAUDE.md §Synthese).
  '## Vraag',
  '## Bevindingen',
  '## Geraadpleegde bronnen',
  '## Lessen',
  '## Open vragen',
];

function scorePage(file) {
  const raw = readFileSync(file, 'utf8');
  const parsed = matter(raw);
  const fm = parsed.data;
  const body = parsed.content;
  const notes = [];
  const isSynthesis = file.includes('/syntheses/');
  const sourceCount = fm.source_count ?? 0;

  // ----- STRUCTURE (0-40) -----
  let structure = 0;

  // (a) H1 — 5 pts
  if (/^# .+/m.test(body)) structure += 5;
  else notes.push('missing H1');

  // (b) Required sections per page type — 10 pts
  if (isSynthesis) {
    const missing = SYNTHESIS_SECTIONS.filter((s) => !body.includes(s));
    if (missing.length === 0) structure += 10;
    else {
      structure += Math.max(0, 10 - 2 * missing.length);
      notes.push(`missing synthesis sections: ${missing.join(', ')}`);
    }
  } else {
    if (sourceCount > 1) {
      if (body.includes('## Debatten en vervanging')) structure += 10;
      else notes.push('missing ## Debatten en vervanging (concept with >1 source)');
    } else {
      structure += 10; // n/a, full points
    }
  }

  // (c) Frontmatter contract — 5 pts
  const requiredFm = ['confidence', 'last_confirmed', 'source_count', 'accessed_at'];
  const missingFm = requiredFm.filter((k) => fm[k] === undefined);
  structure += Math.max(0, 5 - missingFm.length);
  if (missingFm.length > 0) notes.push(`missing frontmatter: ${missingFm.join(', ')}`);

  // (d) Body length ≥200 words — 5 pts
  const wordCount = body.split(/\s+/).filter((w) => w.length > 0).length;
  if (wordCount >= 200) structure += 5;
  else {
    structure += Math.max(0, Math.floor((5 * wordCount) / 200));
    notes.push(`short body: ${wordCount} words (target ≥200)`);
  }

  // (e) No empty sections — 5 pts
  const sectionHeaders = [...body.matchAll(/^(#{2,3} .+)$/gm)];
  let emptySections = 0;
  for (let i = 0; i < sectionHeaders.length; i++) {
    const start = sectionHeaders[i].index + sectionHeaders[i][0].length;
    const end = i + 1 < sectionHeaders.length ? sectionHeaders[i + 1].index : body.length;
    const sectionBody = body.slice(start, end).trim();
    if (sectionBody.length < 20) emptySections++;
  }
  if (emptySections === 0) structure += 5;
  else {
    structure += Math.max(0, 5 - emptySections);
    notes.push(`${emptySections} near-empty section(s)`);
  }

  // (f) Outgoing wikilinks ≥3 — 10 pts
  const wikilinks = [...body.matchAll(WIKILINK_RE)];
  if (wikilinks.length >= 3) structure += 10;
  else {
    structure += Math.max(0, Math.floor((10 * wikilinks.length) / 3));
    notes.push(`few outgoing wikilinks: ${wikilinks.length} (target ≥3)`);
  }

  // ----- CITATION DENSITY (0-30) -----
  let sourceCitations = 0;
  for (const m of wikilinks) {
    const target = normTarget(m[1]).split('/').pop();
    if (SOURCE_SLUG_RE.test(target)) sourceCitations++;
  }
  const density = wordCount > 0 ? (sourceCitations * 1000) / wordCount : 0;
  const citationScore = Math.min(30, Math.floor((30 * density) / 3));
  if (citationScore < 30) {
    notes.push(
      `citation density ${density.toFixed(1)}/1000 words (${sourceCitations} source links in ${wordCount} words; target ≥3.0)`,
    );
  }

  // ----- CROSS-CONSISTENCY (0-30) -----
  let crossConsistency = 30;
  const presentInBody = new Set();
  for (const m of wikilinks) {
    const t = normTarget(m[1]);
    presentInBody.add(t);
    presentInBody.add(t.split('/').pop());
    presentInBody.add(t.replace(/\s+/g, '-'));
  }

  if (Array.isArray(fm.relationships) && fm.relationships.length > 0) {
    let brokenTargets = 0;
    let missingBodyLinks = 0;
    for (const rel of fm.relationships) {
      if (!rel || typeof rel.target !== 'string') continue;
      const t = rel.target.trim();
      const tBase = t.split('/').pop();
      const tNorm = t.replace(/\s+/g, '-');
      if (!knownSlugs.has(t) && !knownSlugs.has(tBase) && !knownSlugs.has(tNorm)) {
        brokenTargets++;
      }
      if (!presentInBody.has(t) && !presentInBody.has(tBase) && !presentInBody.has(tNorm)) {
        missingBodyLinks++;
      }
    }
    if (brokenTargets > 0) {
      crossConsistency -= 5 * brokenTargets;
      notes.push(`${brokenTargets} relationship target(s) don't resolve`);
    }
    if (missingBodyLinks > 0) {
      crossConsistency -= 5 * missingBodyLinks;
      notes.push(`${missingBodyLinks} relationship(s) missing body wikilink (v0.3 rule)`);
    }
  }

  // Broken body wikilinks
  let brokenBodyLinks = 0;
  for (const m of wikilinks) {
    const target = normTarget(m[1]);
    const tBase = target.split('/').pop();
    const tNorm = target.replace(/\s+/g, '-');
    if (!knownSlugs.has(target) && !knownSlugs.has(tBase) && !knownSlugs.has(tNorm)) {
      brokenBodyLinks++;
    }
  }
  if (brokenBodyLinks > 0) {
    crossConsistency -= 2 * brokenBodyLinks;
    notes.push(`${brokenBodyLinks} broken body wikilink(s)`);
  }

  // Debates section for concepts with >1 source (counted again separately)
  if (!isSynthesis && sourceCount > 1 && !body.includes('## Debatten en vervanging')) {
    crossConsistency -= 10;
    // Already noted above
  }

  crossConsistency = Math.max(0, crossConsistency);

  const total = (structure + citationScore + crossConsistency) / 100;
  return {
    file,
    score: Math.round(total * 100) / 100,
    notes,
    breakdown: { structure, citation: citationScore, consistency: crossConsistency },
  };
}

// Minimal-invasive write: replace `quality_score:` line and `quality_notes:` block.
// Preserves all other frontmatter formatting (quotes, key order).
function writeQualityFields(file, score, notes) {
  let content = readFileSync(file, 'utf8');
  if (!content.startsWith('---\n')) return { wrote: false, reason: 'no frontmatter' };
  const fmEnd = content.indexOf('\n---\n', 4);
  if (fmEnd === -1) return { wrote: false, reason: 'unterminated frontmatter' };

  let fm = content.slice(4, fmEnd);
  const bodyPart = content.slice(fmEnd + 1); // includes the closing --- and rest

  // Strip existing quality_score line(s) and quality_notes block(s) (if any).
  // Trailing newline is optional (last frontmatter line has none).
  // Global flag — strip all occurrences, including duplicates from earlier bug.
  fm = fm.replace(/^quality_score:[ \t].*(?:\r?\n|$)/gm, '');
  fm = fm.replace(/^quality_notes:[ \t]*(?:\[[^\]]*\][ \t]*(?:\r?\n|$)|\r?\n(?:[ \t]+-.*\r?\n)+)/gm, '');

  // Build new fields. Single-quote YAML flow list for notes.
  let newFields = `quality_score: ${score}\n`;
  if (notes.length > 0) {
    const escaped = notes.map((n) => "'" + n.replace(/'/g, "''") + "'").join(', ');
    newFields += `quality_notes: [${escaped}]\n`;
  }

  // Compute the "would-be" written content to short-circuit no-op writes.
  const wouldBe = '---\n' + fm.trimEnd() + '\n' + newFields + bodyPart;
  if (wouldBe === content) return { wrote: false, reason: 'no-op' };

  writeFileSync(file, wouldBe);
  return { wrote: true };
}

// ----- DRIVER -----
const candidates = [];
for (const d of TARGET_DIRS) {
  for (const f of walk(join(REPO_ROOT, d))) {
    if (PAGE_ARG && !f.includes(PAGE_ARG)) continue;
    candidates.push(f);
  }
}

const results = candidates.map(scorePage);
results.sort((a, b) => a.score - b.score);

console.log(`${DRY_RUN ? '[DRY-RUN] ' : ''}quality-score.mjs — scored ${results.length} pages`);
console.log('');
console.log('score | S /C /X | path');
console.log('------+---------+-----');
for (const r of results) {
  const rel = r.file.slice(REPO_ROOT.length + 1);
  const b = r.breakdown;
  const s = String(b.structure).padStart(2);
  const c = String(b.citation).padStart(2);
  const x = String(b.consistency).padStart(2);
  console.log(`${r.score.toFixed(2)}  | ${s}/${c}/${x}   | ${rel}`);
}

const dist = { ge85: 0, mid: 0, lt65: 0 };
for (const r of results) {
  if (r.score >= 0.85) dist.ge85++;
  else if (r.score >= 0.65) dist.mid++;
  else dist.lt65++;
}
console.log(`\nDistribution: ≥0.85 = ${dist.ge85}, 0.65–0.85 = ${dist.mid}, <0.65 = ${dist.lt65}`);

if (!DRY_RUN) {
  let wrote = 0;
  let noop = 0;
  for (const r of results) {
    const { wrote: w } = writeQualityFields(r.file, r.score, r.notes);
    if (w) wrote++;
    else noop++;
  }
  console.log(`\nWrites: ${wrote} changed / ${noop} unchanged.`);
}

// Print pages with notes
const flagged = results.filter((r) => r.notes.length > 0);
if (flagged.length > 0 && (PAGE_ARG || DRY_RUN || flagged.length <= 10)) {
  console.log('\nFlagged pages with notes:');
  for (const r of flagged.slice(0, 30)) {
    console.log(`  ${r.file.slice(REPO_ROOT.length + 1)} (${r.score})`);
    for (const n of r.notes) console.log(`    - ${n}`);
  }
  if (flagged.length > 30) console.log(`  ... and ${flagged.length - 30} more`);
}
