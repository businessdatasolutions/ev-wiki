import { QuartzTransformerPlugin } from "../quartz/plugins/types"

// Appends frontmatter `aliases` to the page's searchable text so FlexSearch
// returns the page when a user searches for an alias (e.g. "GenAI" → generative-ai).
//
// Must run after Description (which sets file.data.text).
export const InjectAliases: QuartzTransformerPlugin = () => ({
  name: "InjectAliases",
  htmlPlugins() {
    return [
      () => (_tree, file) => {
        const aliases = file.data.frontmatter?.aliases
        if (!Array.isArray(aliases) || aliases.length === 0) return
        const aliasText = aliases.filter((a) => typeof a === "string").join(" ")
        if (!aliasText) return
        file.data.text = (file.data.text ?? "") + " " + aliasText
      },
    ]
  },
})
