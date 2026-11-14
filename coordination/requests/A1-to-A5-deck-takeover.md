# A1 -> A5: humans asked A1 to take over the deck (Sat ~20:15)

Human request: "take over A5 and make the presentation already". So that A5 can stay on A5-24 (forensics), A1 now
owns **only** `docs/deck/` (index.html, SLIDES.md, assets/). Everything else under `docs/` stays yours.

- Deck v3 is on main: 11 slides, real eval-v2 frame as hero, rule GIFs, h1 and h2 charts drawn to scale with CIs,
  Harbor + red-team table, post-training slide with a dashed **placeholder** for the 07:00 result.
- Numbers come from a fresh local build (`analysis.cli.build_all` on the 652-run export, 17:49 UTC).
  Two changes vs deck v2: eval-v2 h2 Kimi is now 0.523 [0.389, 0.644] (was 0.463), and failure shares are 50% / 44%
  over 194 points (was 46.9% / 42.1% over 99).
- Please point `docs/DEMO_SCRIPT.md` at the new slide numbers (demo = slide 4, gap = 5 and 6) when convenient,
  and send A1 the `bench_summary.json` result when it lands so slide 9 can be filled.
- FYI: `python -m analysis build` fails on Python 3.14 (`argparse: badly formed help string`, probably a `%` in a help
  text); `build_all()` works when called directly.
