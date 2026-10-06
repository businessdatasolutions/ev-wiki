import { QuartzTransformerPlugin } from "../quartz/plugins/types"
import { slugTag } from "../quartz/util/path"

// Adds `type/<type>` and `kind/<kind>` to a page's tags so the graph view
// and tag pages cluster pages by frontmatter type/kind.
//
// Must run after FrontMatter (which populates file.data.frontmatter).
export const InjectTypeTags: QuartzTransformerPlugin = () => ({
  name: "InjectTypeTags",
  markdownPlugins() {
    return [
      () => (_tree, file) => {
        const fm = file.data.frontmatter
        if (!fm) return

        const extraTags: string[] = []
        if (typeof fm.type === "string" && fm.type.trim() !== "") {
          extraTags.push(slugTag(`type/${fm.type.trim()}`))
        }
        if (typeof fm.kind === "string" && fm.kind.trim() !== "") {
          extraTags.push(slugTag(`kind/${fm.kind.trim()}`))
        }

        if (extraTags.length === 0) return
        const existing = fm.tags ?? []
        fm.tags = [...new Set([...existing, ...extraTags])]
      },
    ]
  },
})
