# web/DESIGN.md — visual direction

Owner: A4. A5 follows this for `features/leaderboard` and `features/insights`.
Change requests: `coordination/requests/A5-to-A4-*.md`.

## 1. Direction in one line

**A benchmark ledger with a game cartridge inside it.** The only colourful thing on
the page is the game itself: the 64×64 frame and its 16-colour palette. Everything
around it is quiet, dense, tabular — think sports-stats site or compiler benchmark
table, not a SaaS landing page.

- The frame is the hero. It is drawn crisp (no smoothing), at integer scale, on a
  neutral surface with a 1px hairline border. Nothing overlaps it.
- Chrome is monochrome ink on a flat surface. Colour in the UI means data or
  state, never decoration.
- Density over whitespace. Tables use compact rows; numbers are tabular mono.
- Pixel identity appears in exactly three places: the frame, the wordmark (drawn
  from palette cells), and small "cell swatches" used as legend keys for rules,
  components and players.

## 2. Type

| Role | Font | Size / weight | Notes |
|---|---|---|---|
| UI text | IBM Plex Sans | 14px / 400, 500 | body default 14px, line-height 1.45 |
| Numbers, ids, code | IBM Plex Mono | 13px / 400, 500 | `font-variant-numeric: tabular-nums` everywhere numbers align |
| Page title | IBM Plex Sans | 20px / 600 | one per page, no hero headings |
| Section label | IBM Plex Mono | 11px / 500, uppercase, letter-spacing .06em | the "kicker" above tables and charts |
| Wordmark | pixel cells | — | drawn with `FrameCanvas`-style cells, not a font |

Fonts are bundled through `@fontsource` (works offline at the venue). No other
families. No pixel/retro fonts for text — legibility first.

## 3. Colour tokens

Defined once in `src/design/tokens.css`. Use the token, never a raw hex.
Dark is the default (projector and frame contrast); light is supported via
`[data-theme="light"]` and the OS setting.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg` | `#0e0e0f` | `#f6f6f4` | page |
| `--surface-1` | `#161617` | `#ffffff` | panels, tables |
| `--surface-2` | `#1f1f21` | `#efefec` | hover rows, inputs, selected tab |
| `--line` | `#2c2c2f` | `#dddcd7` | hairlines, table rules, frame border |
| `--line-strong` | `#3d3d42` | `#c3c2bb` | focused inputs, active outline |
| `--text-1` | `#efefec` | `#111111` | primary ink |
| `--text-2` | `#a9a8a2` | `#52514e` | secondary ink, column headers |
| `--text-3` | `#76756f` | `#86857f` | muted: units, timestamps, hints |
| `--accent` | `#ffdc00` | `#8a6d00` | focus ring, active nav underline, current step. Single accent, taken from palette yellow |
| `--good` | `#0ca30c` | `#0ca30c` | WIN, solved |
| `--warn` | `#fab219` | `#fab219` | BUDGET, near limit |
| `--bad` | `#d03b3b` | `#d03b3b` | GAME_OVER, failed |

Status colours always ship with a text label ("WIN", "LOST") or icon — never
colour alone.

### Game palette (16 colours)
Source of truth: `contracts/palette.json` (A2). `src/lib/palette.ts` loads it
and falls back to a built-in copy until it exists. The game palette is **only**
used to draw frames and cell swatches — never as UI chrome.

### Chart colours (categorical — players / models)
From the dataviz reference palette, validated for CVD in fixed order. Assign by
**entity, not rank**: a model keeps its colour on every page (hash of model id
→ slot is NOT allowed; use the order in `models.yaml`, then fold the rest into
"Other").

| Slot | Dark | Light |
|---|---|---|
| 1 | `#3987e5` | `#2a78d6` |
| 2 | `#d95926` | `#eb6834` |
| 3 | `#199e70` | `#1baf7a` |
| 4 | `#c98500` | `#eda100` |
| 5 | `#d55181` | `#e87ba4` |
| 6 | `#008300` | `#008300` |
| 7 | `#9085e9` | `#6250d6` |
| 8 | `#e66767` | `#e34948` |

- Scatter / heatmap forms: max **3** categorical series before folding or faceting.
- Baselines are not categorical series: `optimal`, `human`, `random` are drawn
  as **reference lines** in `--text-2` with dash patterns (solid / long-dash /
  dot) and a direct label.
- Sequential (heatmap, solve rate): single blue ramp `#cde2fb → #0d366b`
  (light), reversed lightness on dark. Diverging (vs. human): blue ↔ red, gray
  midpoint.

## 4. Spacing, shape, layout

- 4px base unit. Tokens `--s1`…`--s8` = 4, 8, 12, 16, 24, 32, 48, 64.
- Radius: **2px** on inputs and buttons, **0** on panels and frames. No pills
  except status chips (radius 2px, not round).
- No shadows. Separation is by hairline (`--line`) and surface step.
- Page: top bar (40px) + content, max width 1600px, 16px gutter (24px ≥ 1024px).
- Grid: 12 columns, 16px gap. A frame panel is never narrower than 384px
  (6× scale) on desktop; 256px (4×) on phone.
- Must read on a 1080p projector at the back of a room: body ≥ 14px, frame ≥ 512px
  on Play and Replay.

## 5. Components (in `src/design/`)

| Primitive | Notes |
|---|---|
| `Panel` | surface-1, 1px line border, optional `label` kicker + right-aligned actions |
| `Button` | 28px tall, mono label for actions (`RESET`, `ACTION1`), sans otherwise; variants `default` / `primary` (accent outline) / `ghost` |
| `Kbd` | key cap for shortcuts: `←` `R` `Space` |
| `Chip` | status: WIN / GAME_OVER / BUDGET / ABORTED, colour + text |
| `Stat` | label kicker + big mono number + unit; used instead of a chart for a single headline |
| `Table` | sticky header, 28px rows, right-aligned numbers, sortable header with ▲▼ text glyph, zebra off, row hover `--surface-2` |
| `Swatch` | 10×10 square of a palette colour, used as a legend key |
| `FrameCanvas` (lib) | 64×64 frame → canvas, integer scale, `image-rendering: pixelated`, optional grid lines and overlay layer |
| `Empty` / `Loading` / `ErrorState` | one line of text + one action, no illustrations |

## 6. Tables

- Numbers right-aligned, mono, tabular. Units in the header ("cost $/game"), not
  in every cell.
- Rank column first, narrow. Model column shows the colour swatch + display
  name + provider in `--text-3`.
- Best value per column in `--text-1` weight 600; everything else 400. No
  green/red cell fills.
- Inline bars allowed (score, solve rate): 4px tall bar under the number,
  series colour, track in `--line`.

## 7. Charts

Library: **Observable Plot** (`@observablehq/plot`) via `src/lib/PlotFigure.tsx`.
Covers scatter, line, heatmap (cell), rule/reference lines and tips.

- One y-axis. Never dual axis.
- Cost axes are **log**. Label units in the axis title.
- Grid lines `--line`, axis text `--text-3` 11px mono.
- Marks: 2px lines, ≥ 8px dots with a 2px `--surface-1` ring, direct labels on
  ≤ 4 series, legend always present for ≥ 2 series.
- Hover tip on every mark (Plot `tip: true`). Every chart has a "table" toggle
  or an adjacent table carrying the same numbers.
- Clicking a mark that represents a run navigates to `/replay/:run`.

## 8. Interaction

- Keyboard first. Play: arrows / WASD, `R` reset, `Space` interact. Replay:
  `←/→` step, `Space` play/pause, `[` `]` speed, `Home/End`.
- Focus ring: 2px `--accent` outline, 1px offset. Never removed.
- Every page has loading, empty and error states.
- URLs are shareable: filters and selected step live in the query string
  (`/replay/abc?step=41`).

## 9. Do / Don't

**Do**
- Let the frame be the only vivid thing on screen.
- Show raw numbers with units; show the baseline next to every model number.
- Show the model's own words (reasoning, hypothesis) verbatim in mono.
- Label what an agent sees vs. what is hidden truth (truth overlay is marked
  "TRUTH — hidden from agents").

**Don't**
- No purple gradients, no gradients at all.
- No emoji as icons. Icons, if any, are 1-colour 16px SVG strokes.
- No glass/blur cards, no drop shadows, no rounded-2xl cards.
- No "hero + three feature cards". The overview page is a table and a frame.
- No colour fills on table cells, no rainbow scales, no dual axes.
- No text inside game frames, no anti-aliased frame scaling.

## 10. `/challenge` and `/kiosk` (booth demo)

The one page read from across a room by people who never saw the project.
Same rules as above, with these exceptions only:
- One headline at 32px / 600 ("Can you beat the AI?") and the verdict line on the
  end screen at 32px. Big numbers (`.ch-big`) at 32px mono. Body text 16px.
- `/kiosk` drops the top bar; the frame may go up to 13× (832px) at 1080p.
- The QR code is black on white with a quiet zone (scanners need it); it is the
  only white block on the page.
- Win/loss on the end screen uses `--good` / `--bad` as a 4px left rule plus the
  words "result · win" / "result · loss"; never colour alone.
- The AI side is always recorded runs, labelled as such ("recorded attempts",
  "average over every recorded attempt"); no live model calls unless an operator
  enables them.
