import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"
import { InjectTypeTags } from "./extensions/inject-type-tags"
import { InjectAliases } from "./extensions/inject-aliases"
import { InjectStaleBanner } from "./extensions/inject-stale-banner"
import { InjectConfidenceBadge } from "./extensions/inject-confidence-badge"
import { InjectVideoLink } from "./extensions/inject-video-link"
import { StripDataview } from "./extensions/strip-dataview"
import { LatexNoSingleDollar } from "./extensions/latex-no-single-dollar"

const config: QuartzConfig = {
  configuration: {
    pageTitle: "EV-Wiki",
    pageTitleSuffix: "",
    enableSPA: true,
    enablePopovers: true,
    analytics: null,
    locale: "nl-NL",
    baseUrl: "businessdatasolutions.github.io/ev-wiki",
    ignorePatterns: [
      "private",
      "templates",
      ".obsidian",
      "raw",
      "**/.DS_Store",
      "**/.graph.json",
    ],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "googleFonts",
      cdnCaching: true,
      typography: {
        header: "Schibsted Grotesk",
        body: "Source Sans Pro",
        code: "IBM Plex Mono",
      },
      colors: {
        lightMode: {
          light: "#faf8f8",
          lightgray: "#e5e5e5",
          gray: "#b8b8b8",
          darkgray: "#4e4e4e",
          dark: "#2b2b2b",
          secondary: "#1e6b4a",
          tertiary: "#84a59d",
          highlight: "rgba(143, 159, 169, 0.15)",
          textHighlight: "#fff23688",
        },
        darkMode: {
          light: "#161618",
          lightgray: "#393639",
          gray: "#646464",
          darkgray: "#d4d4d4",
          dark: "#ebebec",
          secondary: "#6fc79a",
          tertiary: "#84a59d",
          highlight: "rgba(143, 159, 169, 0.15)",
          textHighlight: "#b3aa0288",
        },
      },
    },
  },
  plugins: {
    transformers: [
      Plugin.FrontMatter(),
      InjectTypeTags(),
      InjectStaleBanner(),
      Plugin.CreatedModifiedDate({
        priority: ["frontmatter", "git", "filesystem"],
      }),
      Plugin.SyntaxHighlighting({
        theme: { light: "github-light", dark: "github-dark" },
        keepBackground: false,
      }),
      Plugin.ObsidianFlavoredMarkdown({ enableInHtmlEmbed: false }),
      Plugin.GitHubFlavoredMarkdown(),
      StripDataview(),
      Plugin.TableOfContents(),
      Plugin.CrawlLinks({ markdownLinkResolution: "shortest" }),
      Plugin.Description(),
      InjectConfidenceBadge(),
      InjectVideoLink(),
      InjectAliases(),
      LatexNoSingleDollar(),
    ],
    filters: [Plugin.RemoveDrafts()],
    emitters: [
      Plugin.AliasRedirects(),
      Plugin.ComponentResources(),
      Plugin.ContentPage(),
      Plugin.FolderPage(),
      Plugin.TagPage(),
      Plugin.ContentIndex({
        enableSiteMap: true,
        enableRSS: true,
      }),
      Plugin.Assets(),
      Plugin.Static(),
      Plugin.Favicon(),
      Plugin.NotFoundPage(),
      Plugin.CustomOgImages(),
    ],
  },
}

export default config
