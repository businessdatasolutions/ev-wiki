import {
  QuartzComponent,
  QuartzComponentConstructor,
  QuartzComponentProps,
} from "../quartz/components/types"
import style from "../quartz/components/styles/backlinks.scss"
import { resolveRelative, simplifySlug } from "../quartz/util/path"
import { i18n } from "../quartz/i18n"
import { classNames } from "../quartz/util/lang"
import OverflowListFactory from "../quartz/components/OverflowList"

interface Options {
  hideWhenEmpty: boolean
}

const defaultOptions: Options = { hideWhenEmpty: true }

// Drop-in replacement for the stock Backlinks component that also matches
// pages linking via this page's frontmatter aliases.
//
// The stock component only matches `file.links.includes(canonicalSlug)`.
// With Quartz's alias system, `[[Erik Brynjolfsson]]` resolves to the alias
// slug `Erik-Brynjolfsson`, not the canonical `entities/Erik-Brynjolfsson`,
// so backlinks come up empty for any aliased page.
export default ((opts?: Partial<Options>) => {
  const options: Options = { ...defaultOptions, ...opts }
  const { OverflowList, overflowListAfterDOMLoaded } = OverflowListFactory()

  const Backlinks: QuartzComponent = ({
    fileData,
    allFiles,
    displayClass,
    cfg,
  }: QuartzComponentProps) => {
    const canonical = simplifySlug(fileData.slug!)
    const aliasSlugs = (fileData.aliases ?? []).map((a) => simplifySlug(a))
    const matchSlugs = new Set<string>([canonical, ...aliasSlugs])

    const backlinkFiles = allFiles.filter((file) =>
      file.links?.some((link) => matchSlugs.has(link)),
    )

    if (options.hideWhenEmpty && backlinkFiles.length === 0) return null

    return (
      <div class={classNames(displayClass, "backlinks")}>
        <h3>{i18n(cfg.locale).components.backlinks.title}</h3>
        <OverflowList>
          {backlinkFiles.length > 0 ? (
            backlinkFiles.map((f) => (
              <li>
                <a href={resolveRelative(fileData.slug!, f.slug!)} class="internal">
                  {f.frontmatter?.title}
                </a>
              </li>
            ))
          ) : (
            <li>{i18n(cfg.locale).components.backlinks.noBacklinksFound}</li>
          )}
        </OverflowList>
      </div>
    )
  }

  Backlinks.css = style
  Backlinks.afterDOMLoaded = overflowListAfterDOMLoaded
  return Backlinks
}) satisfies QuartzComponentConstructor<Partial<Options>>
