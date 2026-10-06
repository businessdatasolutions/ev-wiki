import {
  QuartzComponent,
  QuartzComponentConstructor,
  QuartzComponentProps,
} from "../quartz/components/types"

// Melding boven elke pagina (ev-wiki, 06-10-2026). De wiki is publiek, maar het is werkmateriaal:
// getallen komen vaak uit automatische ondertiteling en zijn niet altijd tegen de fabrikant
// gecontroleerd (CLAUDE.md §Getallen uit spraakherkenning). Wie op een pagina landt via een
// zoekmachine, ziet dat meteen. Geen opmaak buiten de site-kleuren, zodat licht en donker kloppen.
export default (() => {
  const WerkmateriaalMelding: QuartzComponent = ({ displayClass }: QuartzComponentProps) => (
    <p class={`werkmateriaal ${displayClass ?? ""}`}>
      Werkmateriaal: een kennisbank die een taalmodel bijhoudt uit reviews en tests. Getallen komen
      vaak uit automatische ondertiteling en zijn niet altijd bij de fabrikant gecontroleerd. Elk feit
      linkt naar zijn bron; kijk daar voor je erop vertrouwt. Actuele prijzen staan op{" "}
      <a href="https://plinkie.nl">plinkie.nl</a>.
    </p>
  )

  WerkmateriaalMelding.css = `
.werkmateriaal {
  font-size: 0.85rem;
  color: var(--darkgray);
  border-left: 3px solid var(--secondary);
  background: var(--highlight);
  padding: 0.5rem 0.75rem;
  margin: 0 0 1rem 0;
}
`
  return WerkmateriaalMelding
}) satisfies QuartzComponentConstructor
