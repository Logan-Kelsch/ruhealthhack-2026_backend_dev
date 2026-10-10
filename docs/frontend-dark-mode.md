# Frontend dark mode

Status: implemented for the prototype, with draft values. The exact palette needs a design pass before the demo.

## What shipped

- **A toggle** on the welcome screen and at the bottom of the sidebar (`ThemeToggle` in `components/ui.tsx`). The choice is stored in `localStorage` under `rounds-theme`; the first visit follows `prefers-color-scheme`. `main.tsx` applies the stored theme before the first render, so there is no flash.
- **Token-based themes.** `index.css` defines the light palette in `@theme` and a `.dark` block with the same token names. Tailwind v4 compiles utilities to `var(--color-*)` (and `color-mix()` for opacity variants), so every screen flips without component changes. Inline `var(--color-*)` uses in SVG properties and style objects flip too.
- **A `panel` token** for the dark hero surfaces. `ink` was doing two jobs: body text and the navy fill behind goal panels, primary buttons, student bubbles and icon tiles. In dark mode body text must lighten while those surfaces stay dark, so the fills moved to `--color-panel` / `--color-panel-hover`.
- **Artwork handling.** `.bg-wash` and `.bg-painting` are dimmed in place under `.dark` (`brightness` and `opacity` in `index.css`). No dark image variants are needed for now.
- **The `dark` variant** is registered (`@custom-variant dark` in `index.css`) for the few element-level exceptions; one is in use, the warn button border in Studio.

Files: `frontend/src/index.css` (themes), `frontend/src/lib/theme.ts` (storage and hook), `frontend/src/components/ui.tsx` (toggle).

## How to work with it

- New colors: add a token to the light `@theme` block and a matching value to `.dark`. Do not write hex values in components.
- New screens: they inherit both themes as long as they use the tokens.
- Vite clears `dist/` on every build, so any manual test page placed there disappears. Serve `dist/` and set `localStorage.rounds-theme` to `dark` to preview.

## What still needs a design pass

- The dark values are drafts. The warm near-black base keeps the palette families, but a designer should confirm the exact tones, especially the panel fill and the indigo accent.
- Twenty-six one-off hex values remain outside the token system: thirteen in the avatar illustration palettes and thirteen decorative (preview art, two status dots, the tree edge, the end-visit hover, the Studio progress bars). Most already work on dark; the tree edge and status dots were checked visually.
- Contrast spot checks done: body text, secondary text, chips, warn rows, rubric pips, tabs, badges. Worth repeating on a real screen (projector gamma differs) before recording.
- Shadows use fixed `rgba(20,27,77,...)` values, so elevation cues disappear on dark. Not fixed; decide if that matters.

## Open questions

1. Design pass on the draft dark values (see table below), then update both blocks in `index.css`.
2. Do we want dark mode in the demo video? It works, but if the room is bright, light mode may project better. The toggle stays regardless.
3. The encounter and mic check have no toggle in their top bars (they stay focused on the visit). Say the word if that changes.

## Reference: draft mapping now in use

| Token | Light | Dark |
|---|---|---|
| `paper` / `wash` | `#f7f6f3` / `#f6f6fa` | `#16161c` / `#1a1a22` |
| `card` / `raised` | `#ffffff` / `#fafafd` | `#1f1f29` / `#262632` |
| `segment` / `chip` / `track` | `#f1f2f7` / `#f4f5f9` / `#eceef5` | `#272733` / `#272733` / `#2b2b38` |
| `panel` / `panel-hover` | `#141b4d` / `#2b3ab8` | `#2c3160` / `#3a4078` |
| `ink` / `ink-soft` / `muted` / `faint` | `#141b4d` / `#4b5285` / `#6a7099` / `#8a8fb3` | `#eeeff4` / `#b9bacb` / `#9a9baf` / `#7d7e93` |
| `line` / `line-2` / `line-3` / `line-4` | `#e7e8f0` / `#dcdfea` / `#e3e4ee` / `#c9cce0` | `#2c2c3a` / `#353545` / `#2f2f3e` / `#3d3d4f` |
| `hair` / `hair-2` | `#f0f1f6` / `#eeeff5` | `#282834` / `#2f2f3e` |
| `indigo` / `indigo-soft` | `#2b3ab8` / `#eef0fd` | `#93a0ff` / `#262a4a` |
| `ok` / `ok-soft` | `#1f7a50` / `#e6f4ec` | `#6fcf9d` / `#1e3529` |
| `warn` / `warn-soft` / `warn-wash` | `#9a5212` / `#fdf1e3` / `#fffaf4` | `#e0a866` / `#3a2b17` / `#2e2416` |
| `danger` / `danger-soft` | `#b42b24` / `#fdecea` | `#f08a82` / `#3a2320` |
