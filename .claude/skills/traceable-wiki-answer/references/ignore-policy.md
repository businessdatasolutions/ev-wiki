# Ignore policy — the triage rubric

Loaded at **Step 3 (Triage)** of `traceable-wiki-answer`. For every candidate in the
ledger emitted by `scripts/wiki-retrieve.mjs`, decide **USE** or **IGNORE** and record exactly
one reason-class. This is what makes requirements 3 (*how it decided to ignore*) and 4 (*what
it ignored*) auditable — the verdict is a reasoning artifact, so it lives in the trace, not in
the script.

## Default posture

- **USE** a candidate when it materially answers one of the decomposed facets *and* is among
  the strongest sources for that facet.
- **IGNORE** otherwise — but every ignore needs a recorded reason-class from the list below.
- Aim for a **focused USE set (typically 4–8 pages)**. A run that marks 30 candidates USE has
  not triaged; it has abdicated. Reading more than ~8 pages usually means the facets are too
  broad — tighten them instead.

## Reason-classes (use one per ignored candidate)

| Reason-class | Fires when | Note |
| --- | --- | --- |
| `below-threshold` | `fused_score` is low and no facet needs the page. | The long tail of graph-only neighbours usually lands here. |
| `decayed` | `effective_confidence < 0.5` **and** a fresher candidate already covers the same facet. | **Never** silently drop a *unique* decayed page — mark it USE and flag the staleness in the answer instead. Decay demotes; it does not delete. |
| `redundant` | Covers the same claim as an already-selected, higher-ranked or higher-confidence page. | MMR-style diversity: keep the stronger page, ignore the echo. Name the page it duplicates. |
| `off-facet` | Semantically adjacent (qmd or graph pulled it in) but addresses none of the decomposed facets. | The most common false positive from pure vector proximity. |
| `superseded` | `status: stale` while its `superseded_by` target is also a candidate. | Per CLAUDE.md §Supersession. USE the successor; ignore the retired page (but you may cite it in §Debates if the contradiction is the point). |
| `wrong-granularity` | An entity catalogue card when the facet needs a claim/figure. | Prefer the concept/source the entity links to. Entity cards are USE only when the facet is genuinely about *who/what* (identity, role, affiliation). |

If two classes both apply, record the **more specific** one (`superseded` > `redundant` >
`decayed` > `off-facet` > `wrong-granularity` > `below-threshold`).

## Signals to read off the ledger

Each candidate carries the fields you need to decide:

- `fused_score` — combined relevance×currency rank hint. Primary triage signal.
- `qmd_rank` / `qmd_score` — was it a genuine search hit (`qmd_rank` non-null) or only reached
  by graph traversal (`qmd_rank: null`, `graph` populated)? Graph-only candidates need a higher
  bar to USE — they are *related to* a hit, not themselves hits.
- `effective_confidence` vs `stored_confidence` — a large gap means the page is read-aged
  (decayed). `null` = a source (evidence; judge by relevance + what it substantiates, not by a
  confidence number).
- `graph[].edge_type` / `via` — *why* the graph linked it. A `contradicts`/`supersedes` edge is
  a strong USE signal even at low `fused_score` (it changes the answer); a `part-of`/`employs`
  edge into an entity card is often `wrong-granularity`.
- `status` / `superseded_by` — supersession flags surfaced from frontmatter.

## What the agent must record (feeds the trace)

For the audit report and JSON trace:

- **USE set** → §Information used + the `[W#]` anchors.
- **IGNORE set** → §Information ignored (one row each: page · reason-class · one-line reason).
- **Which reason-classes actually fired this run** → §Ignore policy applied.

A candidate that was IGNORED then promoted during Step 5 gap-expansion should have its verdict
updated to USE with a note (`promoted: gap-expansion`) — the trace should never contradict the
final answer.
