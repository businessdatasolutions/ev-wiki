#!/usr/bin/env node
// v0.5 quality slice follow-up — wiki-query wrapper for qmd.
//
// Combines two operations in one call:
//   1. `qmd query <query> --json -n <N>` (hybrid + LLM-rerank)
//   2. Bump `accessed_at` on every concept/entity/synthesis page the
//      query returned (per CLAUDE.md §Search "Bumping accessed_at after a query")
//
// This is the procedural stand-in for MCP integration. The MCP server (started
// via `qmd mcp` from a `.mcp.json` registration) gives agents direct `qmd__query`
// access, but doesn't know about the wiki's reinforcement signal — this wrapper
// closes that gap.
//
// Usage:
//   node scripts/wiki-query.mjs "your question"           # default: 8 results, bump
//   node scripts/wiki-query.mjs -n 5 "your question"      # narrow to 5
//   node scripts/wiki-query.mjs --no-bump "your question" # query only, skip bump
//   node scripts/wiki-query.mjs --json "your question"    # raw qmd JSON output
//
// Exit codes: 0 = success; 1 = qmd failure; 2 = bad args.

import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..');

const args = process.argv.slice(2);
let n = 8;
let bump = true;
let rawJson = false;
const remaining = [];
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === '-n') {
    n = parseInt(args[++i], 10);
    if (Number.isNaN(n) || n < 1) {
      console.error('error: -n requires a positive integer');
      process.exit(2);
    }
  } else if (a === '--no-bump') {
    bump = false;
  } else if (a === '--json') {
    rawJson = true;
  } else if (a === '--help' || a === '-h') {
    console.log(
      'Usage: wiki-query.mjs [-n <num>] [--no-bump] [--json] "your question"',
    );
    process.exit(0);
  } else {
    remaining.push(a);
  }
}

if (remaining.length === 0) {
  console.error('error: missing query string');
  console.error('Usage: wiki-query.mjs [-n <num>] [--no-bump] [--json] "your question"');
  process.exit(2);
}

const query = remaining.join(' ');

// ----- Step 1: run qmd query --json -----
const qmd = spawnSync(
  'npx',
  ['--yes', '@tobilu/qmd', 'query', query, '-c', 'ev-wiki', '--json', '-n', String(n)],
  { cwd: REPO_ROOT, encoding: 'utf8' },
);

if (qmd.status !== 0) {
  console.error('qmd failed:');
  console.error(qmd.stderr || qmd.stdout);
  process.exit(1);
}

let results;
try {
  results = JSON.parse(qmd.stdout);
} catch (e) {
  console.error('failed to parse qmd JSON output:', e.message);
  console.error('--- raw stdout ---');
  console.error(qmd.stdout);
  process.exit(1);
}

if (rawJson) {
  console.log(JSON.stringify(results, null, 2));
  process.exit(0);
}

// qmd's JSON structure: { results: [{ path, title, score, snippet, ... }, ...] }
const hits = Array.isArray(results) ? results : results.results || [];

if (hits.length === 0) {
  console.log(`No results for: "${query}"`);
  process.exit(0);
}

// ----- Step 2: pretty-print results -----
console.log(`Query: "${query}"`);
console.log(`Top ${hits.length} result${hits.length === 1 ? '' : 's'}:`);
console.log('');

const bumpCandidates = new Set();
for (let i = 0; i < hits.length; i++) {
  const h = hits[i];
  const path = h.file || h.path || h.uri || '';
  const title = h.title || path;
  const score =
    typeof h.score === 'number'
      ? h.score.toFixed(2)
      : typeof h.rerankScore === 'number'
        ? h.rerankScore.toFixed(2)
        : '—';
  const snippet = (h.snippet || h.content || '').slice(0, 200).replace(/\s+/g, ' ');
  console.log(`  ${i + 1}. [${score}] ${title}`);
  if (path) console.log(`     ${path}`);
  if (snippet) console.log(`     ${snippet}…`);
  console.log('');

  // Collect bump candidates — extract slug from path
  // Path format examples: "qmd://ev-wiki/concepts/foo.md", "wiki/concepts/foo.md", "concepts/foo.md"
  const m = path.match(/(?:^|\/)(?:wiki\/)?(concepts|entities|syntheses)\/([^/]+)\.md$/);
  if (m) bumpCandidates.add(m[2]);
}

// ----- Step 3: bump accessed_at on candidate pages -----
if (bump && bumpCandidates.size > 0) {
  console.log('--- Reinforcement: bumping accessed_at ---');
  const slugs = [...bumpCandidates];
  const bumpResult = spawnSync(
    'node',
    [join(REPO_ROOT, 'scripts/bump-accessed.mjs'), ...slugs],
    { cwd: REPO_ROOT, encoding: 'utf8' },
  );
  process.stdout.write(bumpResult.stdout);
  if (bumpResult.stderr) process.stderr.write(bumpResult.stderr);
} else if (!bump) {
  console.log('(--no-bump given; accessed_at not updated)');
} else {
  console.log('(no concept/entity/synthesis results to bump)');
}
