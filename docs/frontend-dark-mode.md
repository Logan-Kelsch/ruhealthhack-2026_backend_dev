# Frontend dark mode: plan and open questions

Status: hypothesis for discussion, not implemented. Values in the mapping table are drafts, not final palette.

## What the cleanup already made possible

Tailwind v4 turns every `@theme` color into a CSS variable, and the utilities compile to `var()` references. Verified in the built CSS:

- `.bg-paper` compiles to `background-color: var(--color-paper)`.
- Opacity utilities like `bg-card/55` compile to `color-mix(in oklab, var(--color-card) 55%, transparent)` (with a static hex fallback for old browsers).
- Inline `var(--color-*)` uses in SVG properties and style objects resolve at runtime.

That means one override block under a `.dark` class can restyle every screen at once, with no changes in the screen components. This matches the repo rule "colors are design tokens in one file".

The UI cleanup replaced 127 hard-coded color values in `src/` with tokens and introduced `bg-card` for every card, control and glass surface where `bg-white` was used. Twenty-six one-off values remain: thirteen in the avatar illustration palettes (`Avatar.tsx`) and thirteen elsewhere (the end-visit hover shade, two status dots, the order thumbnails, the Studio checklist progress bars, one warn button border, the tree edge stroke, and the ECG/X-ray preview art). Most are decorative or already sit on a dark surface; the tree edge and the two status dots need a contrast check in the dark pass.

## What still blocks a one-block dark theme

1. **`ink` is two roles in one token.** It is body text (`text-ink`) and it is the dark surface for buttons, goal panels and student bubbles (`bg-ink`). In dark mode, text should flip light while those surfaces stay dark. Options:
   - Keep `--color-ink` as the navy surface and add a `--color-text` token for body text, or
   - flip `--color-ink` to the light text color and add `--color-ink-surface` for panels, then update roughly 40 call sites.
   The first option is a smaller diff; the second is cleaner long-term. Needs a team call.
2. **Artwork.** The two background images (`app-wash.png`, `painting.png`) are pastel and sit under every signed-in screen. Dark mode needs either dark image variants or a dark overlay/gradient added in the two `.bg-*` rules. No new assets are needed for the first pass: a filter change and an overlay gradient in `index.css` are enough.
3. **The 13 remaining hard-coded colors** listed above: preview art, avatar faces, two status dots, the end-visit hover, and tree edge strokes. Most can stay as-is on dark; the tree edges and the student-home dot need a contrast check.
4. **Shadows and glass.** Several shadows use `rgba(20,27,77,...)`; on dark surfaces they will be invisible rather than wrong, so this is a polish item. Glass surfaces (`bg-card/55`, `bg-card/70`) inherit the `--color-card` override and keep the blur.
5. **Native controls and selection.** Add `color-scheme: dark` and the selection color override on `.dark` so the search field, textareas and scrollbars match.
6. **Contrast.** The soft status surfaces (chips on cards, warn rows on warn washes) were picked for a light base. Each needs a dark tint pair and a contrast pass.

## Recommended approach

1. Add the variant hook once: `@custom-variant dark (&:where(.dark, .dark *));` in `index.css`. Only needed if we also want `dark:` utilities; the token override works without it.
2. Add a `.dark` block in `index.css` that overrides the token values (same variable names). Every existing utility and inline `var()` reference picks the new values with no component edits.
3. Apply the class to `<html>` from a small theme hook: default from `prefers-color-scheme`, remember the choice in `localStorage`, expose one toggle. Put the toggle in the Shell user card and on the welcome screen; do not add it to the encounter or mic check top bars, which stay focused on the visit.
4. Handle the two pieces that tokens cannot reach: the background artwork rules and `color-scheme`.
5. Run the QA list below on all eleven screens.

Rough effort: step 1-2 with draft values is half a day. Step 3 is a couple of hours. Step 4-5 is half a day including the design pass on values, which needs a team decision per the PRD ("pick one palette with the team before polishing").

### Alternatives considered

- **`dark:` utilities at every call site.** Verbose (hundreds of edits), easy to miss one, and it fights the token rule. No.
- **`prefers-color-scheme` only, no toggle.** Least code, but the demo and the projector decide in the room, not the operating system. A toggle with a system default is barely more work.

## Draft token mapping (needs a design pass)

| Token | Light (today) | Dark (draft) | Note |
|---|---|---|---|
| `paper` | `#f7f6f3` | `#15161e` | warm near-black base |
| `wash` | `#f6f6fa` | `#191b26` | |
| `card` | `#ffffff` | `#1e2130` | cards, controls, glass |
| `raised` | `#fafafd` | `#232637` | row hover, table header |
| `segment`, `chip` | `#f1f2f7`, `#f4f5f9` | `#262a3c` | |
| `track` | `#eceef5` | `#2a2e42` | |
| `ink` (text role) | `#141b4d` | `#edeef7` | see open question 1 |
| `ink-soft` | `#4b5285` | `#b8bdd6` | |
| `muted` / `faint` / `soon` | `#6a7099` / `#8a8fb3` / `#9a9fc0` | `#9aa0bd` / `#7e84a4` / `#666b8a` | |
| `line` / `line-2` | `#e7e8f0` / `#dcdfea` | `#2b2f45` / `#343954` | |
| `line-3` / `line-4` | `#e3e4ee` / `#c9cce0` | `#2f334a` / `#3d4260` | |
| `hair` / `hair-2` | `#f0f1f6` / `#eeeff5` | `#272b40` / `#2b3048` | |
| `indigo` | `#2b3ab8` | `#8f9bff` | lighten for text contrast; keep a deeper fill for buttons if needed |
| `indigo-soft` / `-soft-2` | `#eef0fd` / `#e3e8fd` | `#232849` / `#2a3060` | |
| `indigo-on-ink` | `#a9b6ff` | `#a9b6ff` | already light; check on new surfaces |
| `ok` / `warn` / `danger` | `#1f7a50` / `#9a5212` / `#b42b24` | `#6fcf9d` / `#e0a866` / `#f08a82` | text roles, lighten |
| `ok-soft` / `ok-wash` | `#e6f4ec` / `#f1f9f4` | `#1e3529` / `#1c2d24` | |
| `warn-soft` / `-wash` / `-pill` | `#fdf1e3` / `#fffaf4` / `#fde6cc` | `#3a2b17` / `#2e2416` / `#4a3419` | |
| `danger-soft` / `-bright` | `#fdecea` / `#e2685f` | `#3a2320` / `#ef7f75` | |
| `inactive` | `#a3a7c6` | `#5a607d` | |

The per-screen look should be reviewed before these ship. The mapping keeps the same hue families so screens keep their identity.

## QA checklist for the dark pass

- All eleven screens at 1280x800 and 1440x900.
- Contrast: body text on cards, secondary text on card, chips on cards, warn rows, rubric pips, the decision tree labels and edges.
- Glass sidebar and sticky top bars over the artwork (both), teacher and student variants.
- Focus states on inputs and buttons; selection color; scrollbars in the transcript and tree canvas.
- The welcome painting and the role cards on top of it.
- Projector check before any demo recording: decide whether the demo runs light or dark and set that as the default for the demo machine.

## Open questions

1. `ink` split: text token vs surface token. Smaller diff first, cleaner second. Decide.
2. Should dark mode cover the faculty side, the student side or both? Both is the default answer; the encounter is the screen students use most under time pressure, so it is the one to test hardest.
3. Artwork: dark image variants or overlay? Overlay first is cheaper and reversible.
4. Do we need dark mode for the video at all? The PRD says the team picks a palette before polishing; dark mode is a polish item, not a demo requirement. The cheapest useful outcome is the token override plus a hidden toggle for the demo.
