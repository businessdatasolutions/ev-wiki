import { QuartzTransformerPlugin } from "../quartz/plugins/types"
import { Root as HtmlRoot, Element, ElementContent } from "hast"

// Renders a one-line "watch" strip on every page whose frontmatter `url:`
// points at YouTube — placed immediately after the page's <h1>, so a reader
// on the published site can reach the video the page summarises. Quartz does
// not render frontmatter `url:` anywhere on its own.
//
// Rendered as:
//   ▶ Watch on YouTube · Google Cloud Tech · 30:58
//
// Channel comes from the first `author:` entry (the video convention is
// author = channel); duration is the first MM:SS / H:MM:SS in `length:`.
// Both are optional — the link alone renders when neither is present.
//
// Keyed on the URL rather than `kind: video` so podcast-kind pages whose
// canonical URL is a YouTube upload get the link too.
//
// Implemented as an htmlPlugin registered AFTER Plugin.Description() in
// quartz.config.ts, for the same reason as InjectConfidenceBadge: the strip
// must not leak into og:description / meta description.
const YOUTUBE = /^https?:\/\/(www\.|m\.)?(youtube\.com|youtu\.be)\//i
const DURATION = /(\d{1,2}:\d{2}(?::\d{2})?)/

export const InjectVideoLink: QuartzTransformerPlugin = () => ({
  name: "InjectVideoLink",
  htmlPlugins() {
    return [
      () => (tree: HtmlRoot, file) => {
        const fm = file.data.frontmatter
        if (!fm) return
        const url = typeof fm.url === "string" ? fm.url.trim() : ""
        if (!YOUTUBE.test(url)) return

        const extras: string[] = []
        const author = Array.isArray(fm.author) ? fm.author[0] : fm.author
        if (typeof author === "string" && author.trim() !== "") {
          extras.push(author.trim())
        }
        const duration = typeof fm.length === "string" ? fm.length.match(DURATION) : null
        if (duration) extras.push(duration[1])

        const children: ElementContent[] = [
          { type: "text", value: "▶ " },
          {
            type: "element",
            tagName: "a",
            properties: {
              href: url,
              className: ["external"],
              target: "_blank",
              rel: ["noopener", "noreferrer"],
            },
            children: [{ type: "text", value: "Bekijk op YouTube" }],
          },
        ]
        if (extras.length > 0) {
          children.push({ type: "text", value: ` · ${extras.join(" · ")}` })
        }

        const strip: Element = {
          type: "element",
          tagName: "p",
          properties: { className: ["video-link"] },
          children,
        }

        // Insert immediately after the first <h1> if one exists; otherwise at top.
        const nodes = tree.children
        let insertIndex = 0
        for (let i = 0; i < nodes.length; i++) {
          const node = nodes[i]
          if (node.type === "element" && node.tagName === "h1") {
            insertIndex = i + 1
            break
          }
        }
        nodes.splice(insertIndex, 0, strip)
      },
    ]
  },
})
