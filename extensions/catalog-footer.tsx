import {
  QuartzComponent,
  QuartzComponentConstructor,
  QuartzComponentProps,
} from "../quartz/components/types"
import { FullSlug, resolveRelative } from "../quartz/util/path"
import { version } from "../package.json"
import { i18n } from "../quartz/i18n"

interface Options {
  links: Record<string, string>
}

// The five wiki page types that participate in the catalog count. Order
// mirrors the SessionStart hook (scripts/session-start.mjs) and reads as
// evidence → distilled: sources (evidence) → entities + concepts (catalog)
// → threads (in-flight investigation) → syntheses (durable conclusions).
const COUNTED_TYPES: ReadonlyArray<{ type: string; singular: string; plural: string }> = [
  { type: "source", singular: "source", plural: "sources" },
  { type: "entity", singular: "entity", plural: "entities" },
  { type: "concept", singular: "concept", plural: "concepts" },
  { type: "thread", singular: "thread", plural: "threads" },
  { type: "synthesis", singular: "synthesis", plural: "syntheses" },
]

// Site-wide footer that mirrors the stock Quartz Footer (attribution +
// configured links) and adds a one-line catalog-stats strip computed at
// build time from allFiles. Each count deep-links to its tags/type/<type>
// page — those pages exist because extensions/inject-type-tags.ts auto-stamps
// type/<type> on every wiki page and Quartz's TagPage emitter renders one
// page per tag.
//
// Replaces (not composes with) Component.Footer because SharedLayout.footer
// is a single Component slot.
export default ((opts?: Options) => {
  const CatalogFooter: QuartzComponent = ({
    displayClass,
    cfg,
    fileData,
    allFiles,
  }: QuartzComponentProps) => {
    const year = new Date().getFullYear()
    const links = opts?.links ?? {}

    const counts = new Map<string, number>()
    for (const f of allFiles) {
      const t = f.frontmatter?.type
      if (typeof t === "string" && t.trim() !== "") {
        counts.set(t, (counts.get(t) ?? 0) + 1)
      }
    }

    return (
      <footer class={`${displayClass ?? ""}`}>
        <p>
          {i18n(cfg.locale).components.footer.createdWith}{" "}
          <a href="https://quartz.jzhao.xyz/">Quartz v{version}</a> © {year}
        </p>
        <p class="catalog-stats">
          {COUNTED_TYPES.map(({ type, singular, plural }, idx) => {
            const n = counts.get(type) ?? 0
            const label = n === 1 ? singular : plural
            const href = resolveRelative(fileData.slug!, `tags/type/${type}` as FullSlug)
            return (
              <>
                {idx > 0 ? <span class="catalog-stats-sep"> · </span> : null}
                <a href={href} class="internal">
                  {n} {label}
                </a>
              </>
            )
          })}
        </p>
        <ul>
          {Object.entries(links).map(([text, link]) => (
            <li>
              <a href={link}>{text}</a>
            </li>
          ))}
        </ul>
      </footer>
    )
  }

  CatalogFooter.css = `
.catalog-stats {
  font-size: 0.85rem;
  opacity: 0.85;
  margin: 0.4rem 0 0.6rem;
}
.catalog-stats a.internal {
  background: none;
  padding: 0;
  border-radius: 0;
  border-bottom: 1px dotted var(--gray);
}
.catalog-stats a.internal:hover {
  border-bottom-color: var(--secondary);
}
.catalog-stats .catalog-stats-sep {
  opacity: 0.5;
}
`
  return CatalogFooter
}) satisfies QuartzComponentConstructor
