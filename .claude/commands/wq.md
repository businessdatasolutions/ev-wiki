---
description: Wiki query via qmd hybrid search, with automatic accessed_at bump per §Retention
---

You are answering a query against the LLM wiki in this repo. The user invoked `/wq` with the query as the argument:

**Query:** $ARGUMENTS

Workflow:

1. **Search**: run `node scripts/wiki-query.mjs -n 8 "$ARGUMENTS"` to get the top 8 hits from qmd (hybrid BM25 + vector + LLM-rerank) and **automatically bump `accessed_at`** on every concept / entity / synthesis page that qmd returned. The script prints results in human-readable form and runs the bump as its final step.

2. **Synthesize**: read the actual content of the top 3–5 most relevant hits (use `Read` on the paths printed). The wrapper only shows snippets; the synthesis should be based on full content.

3. **Answer the user's question** in the appropriate language (match the query language — Dutch query → Dutch answer; English query → English answer). Cite each substantive claim with the `[[wikilink|short alias]]` form so the user can follow up.

4. **Surface deferrals**: if the query touches a topic the wiki has gaps on (e.g. an open thread, a low-confidence concept, a `quality_score < 0.65` page), name that explicitly so the user can decide whether to ingest more sources.

5. **Skip the bump only when explicitly told** (e.g. user added `--no-bump` to their query). Default is always to bump — that's the §Retention reinforcement signal.

Conventions:
- The wrapper handles bumping. Do not call `scripts/bump-accessed.mjs` separately unless the user names specific pages outside qmd's hits.
- If qmd returns 0 results, report that — don't fabricate. Suggest a `qmd embed` if pages were recently added without re-indexing.
- For very specific lookup queries (single named entity, exact title), running `node scripts/wiki-query.mjs --no-bump -n 3` is often enough.
