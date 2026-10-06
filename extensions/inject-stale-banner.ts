import { QuartzTransformerPlugin } from "../quartz/plugins/types"
import { Root, Blockquote } from "mdast"

// When a page's frontmatter has `status: stale`, prepend a warning blockquote
// at the top of the page on the published site. Source files stay clean —
// Obsidian still shows the page as-is.
//
// Renders an Obsidian-style callout (`> [!warning] Stale ...`) when
// `superseded_by` is present so the link resolves through CrawlLinks; falls
// back to a plain bold-prefixed blockquote when no successor is set.
//
// Must run after FrontMatter (which populates file.data.frontmatter) and
// before CrawlLinks (which resolves [[wikilinks]]).
export const InjectStaleBanner: QuartzTransformerPlugin = () => ({
  name: "InjectStaleBanner",
  markdownPlugins() {
    return [
      () => (tree: Root, file) => {
        const fm = file.data.frontmatter
        if (!fm) return
        if (typeof fm.status !== "string" || fm.status.trim().toLowerCase() !== "stale") return

        const supersededBy =
          typeof fm.superseded_by === "string" ? fm.superseded_by.trim() : ""

        // Obsidian/Quartz callout: blockquote whose first paragraph starts with
        // `[!warning] Title` followed by a hard break and the body content.
        const headingText = supersededBy
          ? `[!warning] Stale — superseded by [[${supersededBy}]]`
          : `[!warning] Stale`

        const bodyText = supersededBy
          ? "This page is preserved for history but no longer reflects the wiki's current understanding. Follow the link above for the current page."
          : "This page is preserved for history but no longer reflects the wiki's current understanding."

        const banner: Blockquote = {
          type: "blockquote",
          children: [
            {
              type: "paragraph",
              children: [
                { type: "text", value: headingText },
                { type: "break" },
                { type: "text", value: bodyText },
              ],
            },
          ],
        }

        tree.children.unshift(banner)
      },
    ]
  },
})
