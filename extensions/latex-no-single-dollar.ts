import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"
import { QuartzTransformerPlugin } from "../quartz/plugins/types"
import { KatexOptions } from "katex"

interface Options {
  katexOptions: Omit<KatexOptions, "macros" | "output">
  customMacros: { [key: string]: string }
}

// Custom Latex transformer that mirrors quartz/plugins/transformers/latex.ts
// but configures remark-math with `singleDollarTextMath: false`, so `$...$` is
// no longer treated as inline math. Many wiki pages contain dollar amounts
// (e.g. "$285.9B in 2025"); the default behaviour would render the text
// between the two `$` signs in math mode, mangling the asterisks, apostrophes
// and spacing. Display math (`$$...$$`) still works for any future need.
export const LatexNoSingleDollar: QuartzTransformerPlugin<Partial<Options>> = (opts) => {
  const macros = opts?.customMacros ?? {}
  return {
    name: "LatexNoSingleDollar",
    markdownPlugins() {
      return [[remarkMath, { singleDollarTextMath: false }]]
    },
    htmlPlugins() {
      return [[rehypeKatex, { output: "html", macros, ...(opts?.katexOptions ?? {}) }]]
    },
    externalResources() {
      return {
        css: [{ content: "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css" }],
        js: [
          {
            // copy-tex makes copy-paste of math content yield the LaTeX source
            src: "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/copy-tex.min.js",
            loadTime: "afterDOMReady",
            contentType: "external",
          },
        ],
      }
    },
  }
}
