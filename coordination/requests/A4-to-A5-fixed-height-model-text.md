# A4 -> A5: FYI, small edits in your files (human request: model text made the layout jump)

Human (Sat ~18:45): "the agents' thoughts text has variable height, the UI keeps jumping up and down, fix this". A4 fixed it everywhere model text animates, including three of your files (one line each, nothing else touched):
- `features/play/PlayPage.tsx` + `play.css`: `.ghost-hyp` always rendered (non-breaking space when empty), fixed 2-line height.
- `features/replay/replay.css`: `.step-fields` fixed 340px, scrolls inside (reasoning / hypothesis / belief come and go per step).
- `features/overview/OverviewPage.tsx` + `overview.css`: `.ov-hyp` on its own line, always rendered, fixed 2 lines.
Rule for new UI: model text that changes per step goes in a box of fixed height (line clamp + `title` for the full text), never `{text && <p>}`. Measured stable: 22 different hypotheses, one caption height.
