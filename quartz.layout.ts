import { PageLayout, SharedLayout } from "./quartz/cfg"
import * as Component from "./quartz/components"
import BacklinksWithAliases from "./extensions/backlinks-with-aliases"
import RelationshipsPanel from "./extensions/relationships-panel"
import CatalogFooter from "./extensions/catalog-footer"
import WerkmateriaalMelding from "./extensions/werkmateriaal-melding"

export const sharedPageComponents: SharedLayout = {
  head: Component.Head(),
  header: [],
  afterBody: [RelationshipsPanel()],
  footer: CatalogFooter({
    links: {
      GitHub: "https://github.com/businessdatasolutions/ev-wiki",
    },
  }),
}

export const defaultContentPageLayout: PageLayout = {
  beforeBody: [
    Component.ConditionalRender({
      component: Component.Breadcrumbs(),
      condition: (page) => page.fileData.slug !== "index",
    }),
    Component.ArticleTitle(),
    Component.ContentMeta(),
    Component.TagList(),
    WerkmateriaalMelding(),
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        { Component: Component.Search(), grow: true },
        { Component: Component.Darkmode() },
        { Component: Component.ReaderMode() },
      ],
    }),
    Component.Explorer(),
  ],
  right: [
    Component.Graph({
      localGraph: { showTags: true, removeTags: [] },
      globalGraph: { showTags: true, removeTags: [] },
    }),
    Component.DesktopOnly(Component.TableOfContents()),
    BacklinksWithAliases(),
  ],
}

export const defaultListPageLayout: PageLayout = {
  beforeBody: [
    Component.Breadcrumbs(),
    Component.ArticleTitle(),
    Component.ContentMeta(),
    WerkmateriaalMelding(),
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        { Component: Component.Search(), grow: true },
        { Component: Component.Darkmode() },
      ],
    }),
    Component.Explorer(),
  ],
  right: [],
}
