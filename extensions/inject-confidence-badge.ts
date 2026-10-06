import { QuartzTransformerPlugin } from "../quartz/plugins/types"
import { Root as HtmlRoot, Element } from "hast"

// Renders a one-line metadata strip on every page that carries the v0.2
// lifecycle fields (`confidence`, `source_count`, `last_confirmed`) — placed
// immediately after the page's <h1> so it reads as page metadata rather than
// page content.
//
// Rendered as italicized text:
//   Confidence 0.85 · 4 sources · last confirmed 2026-04-28
//
// Skips pages that don't carry confidence (sources, threads, syntheses).
//
// Implemented as an htmlPlugin so the badge is injected into the hast tree
// AFTER Quartz's Description plugin has already computed file.data.description
// from the page text. This prevents the badge text from polluting og:description
// and meta description tags. Must be registered AFTER Plugin.Description() in
// quartz.config.ts.
export const InjectConfidenceBadge: QuartzTransformerPlugin = () => ({
  name: "InjectConfidenceBadge",
  htmlPlugins() {
    return [
      () => (tree: HtmlRoot, file) => {
        const fm = file.data.frontmatter
        if (!fm) return
        if (typeof fm.confidence !== "number") return

        const parts: string[] = []
        parts.push(`Zekerheid ${fm.confidence.toFixed(2).replace(".", ",")}`)

        if (typeof fm.source_count === "number") {
          const noun = fm.source_count === 1 ? "bron" : "bronnen"
          parts.push(`${fm.source_count} ${noun}`)
        }

        if (typeof fm.last_confirmed === "string" && fm.last_confirmed.trim() !== "") {
          parts.push(`laatst bevestigd ${fm.last_confirmed.trim()}`)
        }

        const badgeText = parts.join(" · ")

        const badge: Element = {
          type: "element",
          tagName: "p",
          properties: { className: ["confidence-badge"] },
          children: [
            {
              type: "element",
              tagName: "em",
              properties: {},
              children: [{ type: "text", value: badgeText }],
            },
          ],
        }

        // Insert immediately after the first <h1> if one exists; otherwise at top.
        const children = tree.children
        let insertIndex = 0
        for (let i = 0; i < children.length; i++) {
          const node = children[i]
          if (node.type === "element" && node.tagName === "h1") {
            insertIndex = i + 1
            break
          }
        }
        children.splice(insertIndex, 0, badge)
      },
    ]
  },
})
