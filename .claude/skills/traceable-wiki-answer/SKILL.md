---
name: traceable-wiki-answer
description: Answer a question from the ev-wiki and return a fully auditable trace — the original question, every wiki path explored, what was used vs. ignored (with reasons), where each fact lives, and a mapping from every answer element back to its wiki source. Use when provenance/auditability matters — fact-checking, defensible briefings, "show your work" queries, or any answer that must be traceable to wiki pages. Distinct from /wq (quick lookup) and iterative-wiki-query (Dutch content creation).
argument-hint: "<question>"
---

# Traceable wiki answer

Answer a question against the ev-wiki and produce an **auditable trace**: not just the answer,
but the full provenance — what was explored, what was used, what was ignored and why, where each
fact lives, and which sentence of the answer rests on which wiki page.

This skill exists for the eight things every run must surface:

1. the original question · 2. paths explored · 3. how it decided what to ignore · 4. what it
ignored · 5. what it used · 6. where the used facts live · 7. answer-element → wiki-element
mapping · 8. the final answer.

## When to use / when not

**Use** when provenance matters: fact-checking a claim against the wiki, a defensible briefing,
a "show me exactly where this comes from" request, or any answer someone will audit.

**Don't use** for a trivial single-fact lookup (use `/wq`), or for Dutch publication content
where the goal is a polished post rather than an audit trail (use `iterative-wiki-query`).

## Orchestration

The retrieval math is deterministic and lives in `scripts/wiki-retrieve.mjs`. The **judgement**
— use vs. ignore, and tying answer to evidence — is yours, and it belongs in the visible trace.
Two companion references define the shapes and rules; read them when you reach the step that
cites them:

- `references/ignore-policy.md` — the triage rubric (Step 3).
- `references/trace-schema.md` — the ledger shape, JSON trace, and 8-section report (Steps 2, 7).

### Step 1 — Frame

- Restate the question in one sentence.
- Decompose it into **2–4 facets** (the distinct things that must be answered). Keep them tight;
  broad facets cause over-reading.
- Detect the question's language — the answer (Step 6) matches it; citations stay verbatim.

### Step 2 — Retrieve

Run the **only** retrieval entry point (do not hand-roll qmd calls):

```sh
node scripts/wiki-retrieve.mjs --json -n 12 "<question>"
```

It fuses two streams — qmd hybrid search (relevance) and `wiki/.graph.json` typed-edge
traversal (structure) — via Reciprocal Rank Fusion, then re-ranks by `effective_confidence`
(decay-aware). It prints the **candidate ledger** as JSON (shape in `references/trace-schema.md`)
and bumps `accessed_at` on the qmd-returned concept/entity/synthesis pages as its last step.

- Add `--hops 2` to widen graph traversal for sparse/structural questions.
- If the ledger reports `graph_warning` (graph unavailable), it degraded to qmd-only — note
  that in the trace; the answer is still valid, just without the structural stream.
- If `candidate_count` is 0, report it — don't fabricate. Suggest `npx @tobilu/qmd embed` if
  pages were added recently without re-indexing.

### Step 3 — Triage (the ignore decision)

Read `references/ignore-policy.md`. For **every** candidate, decide **USE** or **IGNORE** and
record one reason-class for each ignore. Lean toward a **focused USE set of 4–8 pages** — graph-
only candidates (`qmd_rank: null`) need a higher bar than genuine search hits. Watch for
`contradicts`/`supersedes` graph edges: those can be USE even at a low `fused_score` because they
change the answer.

Keep the verdict list — it becomes §3, §4, and §5 of the report and the `verdict`/`reason` fields
of the JSON trace.

### Step 4 — Read

`Read` all USE pages in **one parallel tool message** (multiple Read calls in a single block).
Pull the specific spans/sections you'll cite; note the section heading for the answer-element map.

### Step 5 — Gap check (optional, at most one round)

If a facet is still unanswered after reading the USE set, do **one** expansion and document it:

- **index.md fallback** — read `wiki/index.md` to find a page qmd missed by name, or
- **graph hops-2** — re-run Step 2 with `--hops 2`, or seed `wiki/.graph.json` neighbours of a
  strong USE page.

Any page promoted here moves IGNORE→USE in the trace with `promoted: gap-expansion`, and gets its
`accessed_at` bumped in Step 8 (it wasn't in the script's default bump set).

### Step 6 — Synthesize

Write the answer in the question's language. **Every claim carries an inline anchor** `[W1]`,
`[W2]`, … keyed to a USE page. No uncited claims. Where the wiki is thin or a page is decayed,
say so plainly (don't paper over a gap). Citations use `[[slug|short alias]]` and obey the
wikilink-rendering rule — never put markdown inside the alias.

### Step 7 — Emit artifacts

Per `references/trace-schema.md`, write both:

- `inspiration/<YYYY-MM-DD>-<slug>-query-trace.md` — the 8-section audit report.
- `inspiration/<YYYY-MM-DD>-<slug>-query-trace.json` — the machine-readable trace.

Then **check the invariants** (listed in the schema): every `[W#]` resolves to a §6 row and a
USE candidate; every §5 page exists on disk; every §4 row has a reason-class; §4 is non-empty.

Show the user the **Final answer (§7)** in your reply, and link the trace artifacts.

### Step 8 — Reinforce

The retrieve script already bumped the qmd-returned concept/entity/synthesis pages. For any USE
page added during Step 5 gap-expansion (or any USE page that was graph-only), bump it now:

```sh
node scripts/bump-accessed.mjs <slug> [<slug> ...]
```

(Concept/entity/synthesis only — sources don't carry `accessed_at`.)

## Quality checklist

- [ ] Question restated + 2–4 facets named.
- [ ] Retrieval ran via `wiki-retrieve.mjs` (not a hand-rolled qmd call).
- [ ] Every candidate has a USE/IGNORE verdict; every IGNORE has a reason-class.
- [ ] USE set is focused (≈4–8 pages), not the whole ledger.
- [ ] Every answer claim carries a `[W#]` anchor resolving to a USE page.
- [ ] Both artifacts written to `inspiration/` with the date prefix; invariants pass.
- [ ] `accessed_at` bumped on all USE concept/entity/synthesis pages.

## Common mistakes

- **Marking everything USE.** A ledger has 40+ candidates; most are off-facet graph neighbours.
  Triage is the point — an untriaged run fails requirements 3 and 4.
- **Trusting fused_score blindly.** It's a ranking *hint*. A `contradicts` edge or a unique
  decayed source can be USE despite a low score; an irrelevant high-confidence concept is IGNORE
  despite a high one.
- **Uncited sentences in the answer.** Every claim needs a `[W#]`. If you can't anchor it, you
  can't say it.
- **Skipping the JSON trace.** The `.md` is for humans, the `.json` is the reusable provenance —
  both are required.
- **Over-expanding.** Step 5 is at most one round. If two facets are still empty after that, say
  the wiki doesn't cover them rather than spidering the whole graph.
- **Forgetting graph-only USE pages in the bump.** The script only bumps qmd hits; pages you
  promoted from the graph stream need a manual Step 8 bump.
