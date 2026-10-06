import { QuartzTransformerPlugin } from "../quartz/plugins/types"
import { Root } from "mdast"

// Strips ```dataview blocks (and their preceding "## Mentioned in" heading)
// from the markdown AST. Quartz has no Dataview engine, so these blocks would
// otherwise render as literal code on the published site. Source files keep
// the blocks so Obsidian's Dataview plugin still renders them locally.
export const StripDataview: QuartzTransformerPlugin = () => ({
  name: "StripDataview",
  markdownPlugins() {
    return [
      () => (tree: Root) => {
        const children = tree.children
        const drop = new Set<number>()

        for (let i = 0; i < children.length; i++) {
          const node = children[i]
          if (node.type !== "code") continue
          if (node.lang?.toLowerCase() !== "dataview") continue

          drop.add(i)

          // Also drop the immediately preceding "## Mentioned in" heading so
          // we don't leave an empty section behind.
          const prev = i > 0 ? children[i - 1] : null
          if (
            prev &&
            prev.type === "heading" &&
            prev.depth === 2 &&
            prev.children.length === 1 &&
            prev.children[0].type === "text" &&
            prev.children[0].value.trim() === "Mentioned in"
          ) {
            drop.add(i - 1)
          }
        }

        if (drop.size === 0) return
        tree.children = children.filter((_, idx) => !drop.has(idx))
      },
    ]
  },
})
