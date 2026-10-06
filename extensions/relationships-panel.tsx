import {
  QuartzComponent,
  QuartzComponentConstructor,
  QuartzComponentProps,
} from "../quartz/components/types"
import { resolveRelative } from "../quartz/util/path"
import { classNames } from "../quartz/util/lang"

interface Options {
  hideWhenEmpty: boolean
}

const defaultOptions: Options = { hideWhenEmpty: true }

interface Relationship {
  type: string
  target: string
  via?: string
  confidence?: number
}

// Display labels for the closed v0.3 vocabulary. Unknown types fall through
// to their raw string.
const RELATIONSHIP_LABELS: Record<string, string> = {
  "competes-with": "Concurreert met",
  supports: "Ondersteunt",
  contradicts: "Spreekt tegen",
  caused: "Leidde tot",
  fixed: "Loste op",
  supersedes: "Vervangt",
  uses: "Gebruikt",
  "depends-on": "Hangt af van",
  "part-of": "Hoort bij",
  "instance-of": "Is een geval van",
  "authored-by": "Gemaakt door",
  "published-by": "Verschenen via",
  employs: "Heeft in dienst",
}

// Order in which relationship-type groups appear, when present. Types not
// listed appear afterward in insertion order.
const TYPE_ORDER = [
  "competes-with",
  "instance-of",
  "part-of",
  "supports",
  "contradicts",
  "caused",
  "supersedes",
  "uses",
  "depends-on",
  "fixed",
  "authored-by",
  "published-by",
  "employs",
]

// Renders a typed-relationships section at the bottom of the article body
// (registered under `afterBody` in quartz.layout.ts), reading the page's
// `relationships:` frontmatter (v0.3 schema). Targets are matched against
// allFiles by slug basename, so `target: Erik-Brynjolfsson` resolves to the
// entity page at `entities/Erik-Brynjolfsson`. Hides when no relationships
// are defined; an explicit "broken-relationship" span renders when a target
// slug doesn't match any file in the wiki (useful as a lint signal).
//
// Originally lived in the right sidebar but moved to afterBody in v0.3.4 —
// relationships are "related content" and read more naturally at the end of
// the article than as a sidebar widget. Side benefit: no flex/overflow
// gymnastics needed (the page itself is the natural scroll).
export default ((opts?: Partial<Options>) => {
  const options: Options = { ...defaultOptions, ...opts }

  const RelationshipsPanel: QuartzComponent = ({
    fileData,
    allFiles,
    displayClass,
  }: QuartzComponentProps) => {
    const rawRels = fileData.frontmatter?.relationships
    const rels: Relationship[] = Array.isArray(rawRels)
      ? (rawRels as Relationship[]).filter(
          (r) => r && typeof r.type === "string" && typeof r.target === "string",
        )
      : []

    if (rels.length === 0) {
      if (options.hideWhenEmpty) return null
    }

    // Group by type, preserving insertion order within each type
    const byType = new Map<string, Relationship[]>()
    for (const rel of rels) {
      const list = byType.get(rel.type) ?? []
      list.push(rel)
      byType.set(rel.type, list)
    }

    // Sort types by TYPE_ORDER, with unknown types appended in insertion order
    const orderedTypes = [
      ...TYPE_ORDER.filter((t) => byType.has(t)),
      ...Array.from(byType.keys()).filter((t) => !TYPE_ORDER.includes(t)),
    ]

    if (orderedTypes.length === 0) {
      if (options.hideWhenEmpty) return null
    }

    // Match a relationship target (e.g. "Erik-Brynjolfsson" or
    // "ai-employment-effects") against a file in allFiles. Try exact slug,
    // then slug basename match.
    const findTargetFile = (target: string) => {
      const normalized = target.replace(/\s+/g, "-")
      return allFiles.find((f) => {
        if (!f.slug) return false
        if (f.slug === normalized) return true
        const basename = f.slug.split("/").pop() ?? f.slug
        return basename === normalized
      })
    }

    return (
      <section class={classNames(displayClass, "relationships-panel")}>
        <h2>Relationships</h2>
        {orderedTypes.map((type) => {
          const list = byType.get(type) ?? []
          return (
            <div class="relationships-group">
              <h3>{RELATIONSHIP_LABELS[type] ?? type}</h3>
              <ul>
                {list.map((rel) => {
                  const targetFile = findTargetFile(rel.target)
                  const targetTitle =
                    (targetFile?.frontmatter?.title as string | undefined) ?? rel.target
                  const href =
                    targetFile?.slug && fileData.slug
                      ? resolveRelative(fileData.slug, targetFile.slug)
                      : null
                  return (
                    <li>
                      {href ? (
                        <a href={href} class="internal">
                          {targetTitle}
                        </a>
                      ) : (
                        <span class="broken-relationship">{rel.target}</span>
                      )}
                      {rel.via ? (
                        <span class="relationship-via">
                          {" — "}
                          <em>{rel.via}</em>
                        </span>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        })}
      </section>
    )
  }

  // Body section style — registered in afterBody, so the page itself is the
  // natural scroll. No flex/overflow gymnastics needed.
  RelationshipsPanel.css = `
.relationships-panel {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--lightgray);
}
.relationships-panel > h2 {
  font-size: 1.4rem;
  margin: 0 0 1rem;
}
.relationships-panel .relationships-group + .relationships-group {
  margin-top: 1rem;
}
.relationships-panel .relationships-group > h3 {
  font-size: 0.8rem;
  margin: 0 0 0.4rem;
  opacity: 0.7;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}
.relationships-panel .relationships-group > ul {
  list-style: disc;
  padding-left: 1.5rem;
  margin: 0;
}
.relationships-panel .relationships-group > ul > li {
  margin: 0.35rem 0;
  line-height: 1.5;
}
.relationships-panel .relationship-via {
  opacity: 0.7;
}
.relationships-panel .broken-relationship {
  opacity: 0.5;
  font-style: italic;
}
`

  return RelationshipsPanel
}) satisfies QuartzComponentConstructor<Partial<Options>>
