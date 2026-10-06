#!/usr/bin/env node
// lint-collapse.mjs — detect CONTEXT COLLAPSE on concept and synthesis pages.
//
// Why this exists
// ---------------
// Every ingest rewrites the concept pages it touches (CLAUDE.md §Process step 6). ACE
// (Zhang et al. 2025, arXiv:2510.04618) names the two failure modes of exactly that
// pattern: BREVITY BIAS (each rewrite prefers a tidier summary) and CONTEXT COLLAPSE
// (iterative rewriting erodes detail over time). A page that has absorbed ten ingests
// has been rewritten ten times, and nothing in this repo has ever checked whether it
// came out the other side with more knowledge or less.
//
// Git already holds the evidence. This script reads it.
//
// What it flags
// -------------
//   A. Per-revision collapse — body word count fell >= --drop (default 10%) in a single
//      commit while `source_count` did NOT fall. More sources, fewer words: the page
//      absorbed evidence and got shorter.
//   B. Lifetime shrink — current body is below --floor (default 85%) of the page's
//      historical peak, while source_count is at or above what it was at that peak.
//   C. Dropped wikilinks — a [[target]] present at the peak revision is absent now,
//      although the target page still exists and the page records no supersession.
//
// None of these is automatically a defect: a genuine cleanup of a padded page looks
// identical to collapse from the outside. This is a READ-ONLY lint that reports and
// lets a human judge, in line with CLAUDE.md §Hooks ("no auto-fix on lint warnings").
//
// Usage:
//   node scripts/lint-collapse.mjs                    # concepts + syntheses
//   node scripts/lint-collapse.mjs --page agent-harness
//   node scripts/lint-collapse.mjs --drop 0.15 --floor 0.9
//   node scripts/lint-collapse.mjs --json
//
// Exit codes: 0 = clean, 1 = findings reported, 2 = bad args.

import { spawnSync } from 'node:child_process';
import { readdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join, basename } from 'node:path';
import matter from 'gray-matter';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');
const SCAN_DIRS = ['wiki/concepts', 'wiki/syntheses'];

const USAGE =
  'Usage: lint-collapse.mjs [--page <slug>] [--drop 0..1] [--floor 0..1] [--max-revs <n>] [--json]';

let onlyPage = null;
let DROP = 0.1; // per-revision word-loss threshold
let FLOOR = 0.85; // lifetime floor, as a fraction of peak
let MAX_REVS = 60;
let asJson = false;
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--page') onlyPage = argv[++i];
  else if (a === '--drop') DROP = num(argv[++i], '--drop');
  else if (a === '--floor') FLOOR = num(argv[++i], '--floor');
  else if (a === '--max-revs') MAX_REVS = parseInt(argv[++i], 10) || 60;
  else if (a === '--json') asJson = true;
  else if (a === '--help' || a === '-h') (console.log(USAGE), process.exit(0));
  else bail(`unknown argument: ${a}`);
}
function bail(m) {
  console.error(`error: ${m}`);
  console.error(USAGE);
  process.exit(2);
}
function num(raw, flag) {
  const v = Number(raw);
  if (!Number.isFinite(v) || v < 0 || v > 1) bail(`${flag} must be a number in [0, 1]`);
  return v;
}

function git(args, opts = {}) {
  const r = spawnSync('git', args, { cwd: REPO_ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, ...opts });
  return r.status === 0 ? r.stdout : null;
}

// Body = everything after the frontmatter. Word count ignores markdown punctuation-only tokens.
function bodyStats(raw) {
  let data = {};
  let content = raw;
  try {
    const parsed = matter(raw);
    data = parsed.data || {};
    content = parsed.content || '';
  } catch {
    /* unparseable frontmatter on an old revision: fall back to whole file */
  }
  const words = content.split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;
  const links = new Set();
  for (const m of content.matchAll(/\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]/g)) {
    links.add(m[1].trim());
  }
  return { words, links, sourceCount: typeof data.source_count === 'number' ? data.source_count : null, data };
}

// All revisions of one path, oldest first, as {sha, date, blob}.
function revisions(relPath) {
  const log = git(['log', '--follow', '--format=%H\t%ad', '--date=short', '--', relPath]);
  if (!log) return [];
  const rows = log.trim().split('\n').filter(Boolean).map((l) => {
    const [sha, date] = l.split('\t');
    return { sha, date };
  });
  rows.reverse(); // oldest first
  return rows.slice(-MAX_REVS);
}

// Read each revision's blob in ONE cat-file process rather than one `git show` per commit.
function readRevisions(relPath, revs) {
  if (revs.length === 0) return [];
  const specs = revs.map((r) => `${r.sha}:${relPath}`).join('\n') + '\n';
  // No `encoding` option: spawnSync then hands back Buffers, which is what the
  // length-prefixed cat-file --batch protocol needs (byte offsets, not code points).
  const r = spawnSync('git', ['cat-file', '--batch'], {
    cwd: REPO_ROOT,
    input: Buffer.from(specs, 'utf8'),
    maxBuffer: 256 * 1024 * 1024,
  });
  if (r.status !== 0) return [];
  const buf = r.stdout;
  const out = [];
  let off = 0;
  for (const rev of revs) {
    const nl = buf.indexOf(0x0a, off);
    if (nl === -1) break;
    const header = buf.slice(off, nl).toString('utf8');
    off = nl + 1;
    const parts = header.split(' ');
    if (parts.length < 3) continue; // "<spec> missing" — path renamed at this revision
    const size = parseInt(parts[2], 10);
    const content = buf.slice(off, off + size).toString('utf8');
    off += size + 1; // trailing newline
    out.push({ ...rev, ...bodyStats(content) });
  }
  return out;
}

const pageExists = (target) => {
  for (const d of ['concepts', 'entities', 'syntheses', 'sources', 'threads']) {
    if (existsSync(join(REPO_ROOT, 'wiki', d, `${target}.md`))) return true;
  }
  // wikilinks may carry a folder prefix, e.g. [[concepts/agent-harness]]
  return existsSync(join(REPO_ROOT, 'wiki', `${target}.md`));
};

// ----- scan -----
const files = [];
for (const dir of SCAN_DIRS) {
  const abs = join(REPO_ROOT, dir);
  if (!existsSync(abs)) continue;
  for (const f of readdirSync(abs)) {
    if (!f.endsWith('.md')) continue;
    if (onlyPage && basename(f, '.md') !== onlyPage) continue;
    files.push(`${dir}/${f}`);
  }
}
if (files.length === 0) bail(onlyPage ? `no page matched --page ${onlyPage}` : 'no pages to scan');

const findings = [];
const sizes = [];
let scanned = 0;
for (const relPath of files) {
  const revs = readRevisions(relPath, revisions(relPath));
  if (revs.length < 2) continue;
  scanned++;
  const slug = basename(relPath, '.md');
  const current = revs[revs.length - 1];
  const events = [];

  // A — per-revision collapse
  for (let i = 1; i < revs.length; i++) {
    const prev = revs[i - 1];
    const cur = revs[i];
    if (prev.words === 0) continue;
    const delta = (prev.words - cur.words) / prev.words;
    const sourcesHeld =
      prev.sourceCount === null || cur.sourceCount === null || cur.sourceCount >= prev.sourceCount;
    if (delta >= DROP && sourcesHeld) {
      events.push({
        kind: 'revision-collapse',
        date: cur.date,
        sha: cur.sha.slice(0, 9),
        words_before: prev.words,
        words_after: cur.words,
        pct: Math.round(delta * 100),
        source_count_before: prev.sourceCount,
        source_count_after: cur.sourceCount,
      });
    }
  }

  // B — lifetime shrink against the peak
  let peak = revs[0];
  for (const r of revs) if (r.words > peak.words) peak = r;
  const belowFloor = peak.words > 0 && current.words < FLOOR * peak.words;
  const sourcesGrew =
    peak.sourceCount === null ||
    current.sourceCount === null ||
    current.sourceCount >= peak.sourceCount;
  if (belowFloor && sourcesGrew && peak.sha !== current.sha) {
    events.push({
      kind: 'lifetime-shrink',
      peak_date: peak.date,
      peak_words: peak.words,
      current_words: current.words,
      pct: Math.round((1 - current.words / peak.words) * 100),
      source_count_at_peak: peak.sourceCount,
      source_count_now: current.sourceCount,
    });

    // C — wikilinks lost since the peak (only meaningful when the page did shrink)
    const supersedes = JSON.stringify(current.data.supersedes || '') + JSON.stringify(current.data.superseded_by || '');
    const lost = [...peak.links].filter(
      (l) => !current.links.has(l) && pageExists(l) && !supersedes.includes(l),
    );
    if (lost.length > 0) {
      events.push({ kind: 'dropped-wikilinks', since: peak.date, targets: lost.sort() });
    }
  }

  if (events.length > 0) {
    findings.push({ page: relPath, slug, revisions: revs.length, events });
  }

  sizes.push({
    page: relPath,
    words: current.words,
    source_count: current.sourceCount,
    growth: peak.words > 0 ? Math.round((current.words / revs[0].words) * 10) / 10 : null,
    words_per_source: current.sourceCount ? Math.round(current.words / current.sourceCount) : null,
  });
}

// ----- report -----
// The counterpart signal. Collapse is one way a rewritten page goes wrong; unbounded
// accretion is the other, and it is invisible to every threshold above. Printing the
// heaviest pages turns a clean run into information rather than just a green tick.
function heaviest(n = 5) {
  return [...sizes].sort((a, b) => b.words - a.words).slice(0, n);
}

if (asJson) {
  console.log(
    JSON.stringify(
      { scanned, pages_flagged: findings.length, drop: DROP, floor: FLOOR, findings, heaviest: heaviest(10) },
      null,
      2,
    ),
  );
  process.exit(findings.length > 0 ? 1 : 0);
}

function printHeaviest() {
  console.log('Heaviest pages (accretion is the opposite failure mode, and unchecked):');
  for (const p of heaviest()) {
    const wps = p.words_per_source !== null ? `, ${p.words_per_source} w/source` : '';
    const g = p.growth !== null ? `, ${p.growth}x since first revision` : '';
    console.log(`  ${String(p.words).padStart(6)} words  ${p.page}${wps}${g}`);
  }
}

if (findings.length === 0) {
  console.log(`lint-collapse: no collapse signals across ${scanned} page(s) with history.`);
  console.log('');
  printHeaviest();
  process.exit(0);
}

console.log(`lint-collapse: ${findings.length} of ${scanned} page(s) show collapse signals.`);
console.log(`(thresholds: per-revision drop >= ${Math.round(DROP * 100)}%, lifetime floor ${Math.round(FLOOR * 100)}% of peak)\n`);
for (const f of findings) {
  console.log(`${f.page}  (${f.revisions} revisions)`);
  for (const e of f.events) {
    if (e.kind === 'revision-collapse') {
      const sc =
        e.source_count_before !== null && e.source_count_after !== null
          ? `, source_count ${e.source_count_before} -> ${e.source_count_after}`
          : '';
      console.log(`  - [${e.date} ${e.sha}] body ${e.words_before} -> ${e.words_after} words (-${e.pct}%)${sc}`);
    } else if (e.kind === 'lifetime-shrink') {
      const sc =
        e.source_count_at_peak !== null && e.source_count_now !== null
          ? `, source_count ${e.source_count_at_peak} -> ${e.source_count_now}`
          : '';
      console.log(`  - lifetime: peak ${e.peak_words} words on ${e.peak_date}, now ${e.current_words} (-${e.pct}%)${sc}`);
    } else if (e.kind === 'dropped-wikilinks') {
      console.log(`  - wikilinks present at peak (${e.since}) and gone now: ${e.targets.map((t) => `[[${t}]]`).join(', ')}`);
    }
  }
  console.log('');
}
printHeaviest();
console.log('');
console.log('These are signals, not verdicts — a genuine cleanup looks the same from outside.');
console.log('Read the diff before acting: git log -p -- <page>');
process.exit(1);
