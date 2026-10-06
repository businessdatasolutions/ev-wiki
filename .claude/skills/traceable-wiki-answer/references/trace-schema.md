# Trace schema — ledger in, audit artifacts out

This file defines the three shapes the skill works with:

1. the **candidate ledger** emitted by `scripts/wiki-retrieve.mjs` (input to triage),
2. the **JSON trace** the skill writes (machine-readable provenance), and
3. the **Markdown audit report** the skill writes (the 8 traceability sections).

Both artifacts go to `inspiration/<YYYY-MM-DD>-<slug>-query-trace.{json,md}` where `<slug>` is a
short kebab-case slug of the question and `<YYYY-MM-DD>` is today.

---

## 1. Candidate ledger (output of `wiki-retrieve.mjs --json`)

```jsonc
{
  "query": "what is the agent harness",
  "generated_at": "2026-06-05T10:12:22.479Z",
  "params": { "seeds": 12, "hops": 1, "k_rrf": 60, "graph_w": 0.5, "conf_floor": 0.6, "today": "2026-06-05" },
  "graph_available": true,
  "graph_warning": null,                 // string if the graph degraded to qmd-only
  "qmd_hit_count": 12,
  "candidate_count": 48,
  "candidates": [
    {
      "slug": "concepts/agent-harness",
      "path": "wiki/concepts/agent-harness.md",
      "type": "concept",                 // concept | entity | synthesis | source | thread
      "title": "agent-harness",
      "qmd_rank": 1,                      // null when the page was reached only via the graph
      "qmd_score": 0.93,                  // null when graph-only
      "graph": [                          // empty when the page was a pure qmd hit
        { "from_seed": "concepts/ai-agents", "edge_type": "uses", "via": "…", "hops": 1 }
      ],
      "stored_confidence": 0.98,          // null on sources (no confidence field)
      "accessed_at": "2026-06-02",
      "last_confirmed": "2026-06-02",
      "days_since_access": 3,
      "effective_confidence": 0.97,       // confidence × exp(-days/tau); null when no stored confidence
      "rrf_score": 0.0328,
      "fused_score": 0.99,                // relNorm × (conf_floor + (1-conf_floor)·confTerm)
      "retrieval_reasons": ["qmd rank 1 (score 0.93)", "graph: concepts/ai-agents -->uses--> this (1 hop)"],
      "status": "stale",                  // present only if frontmatter carries it
      "superseded_by": "[[…]]"            // present only if frontmatter carries it
    }
  ]
}
```

Candidates are pre-sorted by `fused_score` descending. The script does **not** assign verdicts —
the agent adds `verdict` + `reason` during triage (per `ignore-policy.md`).

---

## 2. JSON trace (written by the skill)

The ledger, enriched with verdicts, the answer-element map, and the final answer text.

```jsonc
{
  "question": { "original": "…", "restated": "…", "facets": ["…", "…"], "language": "en" },
  "params": { /* copied from the ledger */ },
  "graph_available": true,
  "candidates": [
    { /* every ledger candidate, plus: */
      "verdict": "use",                   // "use" | "ignore"
      "reason": "top qmd hit; defines the concept directly",
      "reason_class": null,               // null for USE; one ignore-policy class for IGNORE
      "promoted": null                    // "gap-expansion" if it moved IGNORE→USE in Step 5
    }
  ],
  "expansions": [                          // Step 5 gap-checks, empty if none
    { "trigger_facet": "…", "method": "index.md" | "graph-hops-2", "added": ["concepts/…"] }
  ],
  "answer_map": [
    { "anchor": "W1", "claim": "…", "pages": ["concepts/agent-harness"], "span": "## Working definition" }
  ],
  "answer": "…full answer text with [W#] anchors…",
  "generated_at": "2026-06-05T…Z"
}
```

---

## 3. Markdown audit report (written by the skill)

Frontmatter then the **eight sections in this exact order**. The bracketed `(req N)` tags map to
the eight user requirements; do not print them in the artifact.

```markdown
---
type: query-trace
question: "<original question, one line>"
date: YYYY-MM-DD
language: <en|nl|…>
trace: "<slug>-query-trace.json"
pages_used: <N>
pages_ignored: <M>
---

# Query trace — <short title>

## 1. Question                                    (req 1)
- **Original:** <verbatim question>
- **Restated:** <one sentence>
- **Facets:** 1) … 2) … 3) …

## 2. Paths explored                              (req 2 + 6)
Grouped by retrieval source. Every wiki path the run touched, with where it lives.

**qmd hits** (relevance stream)
| # | Page | type | qmd score | fused | verdict |
|---|------|------|-----------|-------|---------|
| 1 | `wiki/concepts/agent-harness.md` | concept | 0.93 | 0.99 | USE |

**graph neighbours** (`--hops N`, typed-edge stream)
| Page | reached via | hops | fused | verdict |
|------|-------------|------|-------|---------|
| `wiki/sources/…md` | concepts/ai-agents --uses--> this | 1 | 0.47 | IGNORE |

**index.md / gap-expansion** (Step 5, if any)
| Page | why added |
|------|-----------|

## 3. Ignore policy applied                       (req 3)
The reason-classes that actually fired this run, each with the rule in one line.
- `below-threshold` — …
- `redundant` — …

## 4. Information ignored                          (req 4)
| Page | reason-class | one-line reason |
|------|--------------|-----------------|
| `wiki/sources/…md` | off-facet | adjacent to harness but about pricing, not definition |

## 5. Information used                             (req 5)
| Page | type | effConf | contribution |
|------|------|---------|--------------|
| `wiki/concepts/agent-harness.md` | concept | 0.97 | working definition + the 7-block stack |

## 6. Answer-element map                           (req 7)
| Anchor | Answer element (claim) | Wiki page(s) | Section / span used |
|--------|------------------------|--------------|---------------------|
| [W1] | the harness is the runtime scaffold around the model | [[concepts/agent-harness]] | ## Working definition |

## 7. Final answer                                 (req 8 + restates req 1)
<answer in the question's language, every claim carrying an inline [W#] anchor that resolves to
a row in §6; no uncited claims>

## 8. Trace artifact
Machine-readable provenance: [`<slug>-query-trace.json`](<slug>-query-trace.json)
```

### Invariants the artifacts must satisfy (checked at Step 7)

- Every `[W#]` in §7 resolves to a row in §6 **and** to a `verdict: "use"` candidate in the JSON.
- Every page in §5 exists on disk and appears in §2.
- Every row in §4 carries a reason-class drawn from `ignore-policy.md`.
- §4 is non-empty in any non-trivial run (if nothing was ignored, the facets were too narrow or
  the ledger too small — note why).
- Citations in §7 use `[[slug|alias]]` form and obey the wikilink-rendering rule (no markdown
  inside the alias).
