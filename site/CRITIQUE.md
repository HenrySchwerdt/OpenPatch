# Why the first OpenPatch site looked amateur

Written after screenshotting the previous build at 1440 and 375 px. Blunt on purpose.

## The product never looked real
- The hero was an interactive three.js scene inside a **boxed, gridded frame** with corner brackets and a "FIG. 01" caption. It reads as an engineering demo, not a product.
- The model was a white lid on a black slab with **flat lighting and no material response**. The internals were procedural cuboids and cylinders, so the "exploded view" looked like toy blocks.
- Nothing carried weight: no soft contact shadow, no edge highlight, no sense of a moulded, soft-touch surface.

## Too many boxes, too many rules
- Every idea sat inside an outlined rectangle: the 3D viewer, each diagram, each stat, each card. Borders everywhere meant nothing had hierarchy, because everything had the same emphasis.
- Hairline dividers between every section and a grid-paper background made the page feel like a spec sheet.

## Shouting typography
- Hero set in ultra-heavy, tightly tracked grotesk, three lines, with the last in orange: "Flach. Offen. Abnehmbar." The type was loud but said little.
- Monospace micro-labels ("§ 03 / WIE ES FUNKTIONIERT", "FIG. 01", axis captions) in every block added noise and a pseudo-technical tone that the product has not earned.
- Mixed scales with no rhythm: huge headline, then small grey paragraphs, then tiny mono text.

## The orange warning bar dominated
- A full-width saturated orange bar at the very top of every screen, in monospace, carried the safety disclaimer. It was the loudest object on the page, above the product and above the brand. Safety is serious, but shouting it in the nav slot reads as panic, not care. A calm notice plus a proper Safety section does the job better.
- The same orange was then reused for the CTA, headline accent, diagram highlights and links, so it stopped meaning anything.

## Cramped spacing, no negative space
- Content sat in a 1360 px wrapper with moderate padding; sections ran into each other. Premium pages earn their feel from emptiness, and this one had almost none.
- On mobile the warning bar plus header consumed roughly 120 px before any content appeared; the hero then stacked a headline, paragraph and two buttons before the product was visible.

## Diagrams looked like a student schematic
- Hand-drawn SVG with dashed outlines, monospace labels overlapping their own shapes (the "30G needle" label sits on the line it names) and a sticky header overlapping a diagram.
- Each diagram lived in its own bordered box with a caption saying "schematic, not to scale". That reads as unfinished.

## Language
- The whole site was German while the project is now English-first. The tone was a mix of marketing and spec dump.

## What the redesign does instead
1. Real path-traced renders (SolidCraft) of the actual CAD, in soft-touch white and graphite, exploded and top-down.
2. Alternating white / light grey / black sections, one blue accent for links and the single CTA, no borders on content.
3. One neutral variable grotesk (Inter, optical size axis) at big, calm, centred scales.
4. Scroll story instead of a widget: the shell separates into its parts as you scroll.
5. An interactive 3D model, but behind a "View in 3D" button, lazy-loaded, lit with an environment map and a soft shadow.
6. A calm notice at the top and a dedicated Safety section; no alarm colours.
7. Size comparison drawn to scale with clean silhouettes.
