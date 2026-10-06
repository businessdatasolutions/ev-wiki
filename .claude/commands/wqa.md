---
description: Auditable wiki answer — runs the traceable-wiki-answer skill (question, paths explored, used vs. ignored with reasons, answer-element→page map, final answer)
argument-hint: "<question>"
---

The user invoked `/wqa` to get a **fully traceable answer** from the LLM wiki in this repo.

**Question:** $ARGUMENTS

Use the **`traceable-wiki-answer`** skill to handle this end to end. It will: frame the question
into facets, retrieve via `node scripts/wiki-retrieve.mjs --json -n 12 "$ARGUMENTS"` (qmd ∪ graph,
RRF-fused, decay-ranked), triage every candidate USE/IGNORE per the ignore policy, read the USE
pages, synthesize an answer with `[W#]` anchors, and write both an 8-section Markdown audit report
and a JSON trace to `inspiration/<date>-<slug>-query-trace.{md,json}`.

Invoke the skill now (do not hand-roll the retrieval). Reply with the **Final answer** section and
links to the two trace artifacts.

Distinct from `/wq` (quick lookup, no audit trail).
