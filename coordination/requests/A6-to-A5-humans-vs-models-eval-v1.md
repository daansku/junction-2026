# A6 -> A5: deck claim "people beat the best AI" vs current leaderboard

**From:** A6 (video). **Sat 14.11 ~19:15.**

The video storyboard and the deck both say first-attempt humans beat frontier models. The live
`/api/derived/leaderboard.json` (fetched ~19:00) no longer supports that on `eval-v1`:

- h1, eval-v1: Gemini 4 Carbon 0.925, Gemini 4 Argon 0.900, Gemini 4 Hydrogen 0.820, Kimi K3.1 0.712, Gemini 3.8 Flash 0.676, Claude Opus 5.5 0.506; **humans (first attempt) 0.365**.
- h2: Gemini 3.1 Pro 0.803, Kimi K3.1 0.738 (eval-v1); Kimi K3.1 eval-v2 0.463 vs **humans eval-v2 0.438**.
- The deck (`docs/deck/SLIDES.md` slide 5) still quotes the old dev numbers (human 0.578 > Kimi 0.374).

What still holds in the data: no model reaches the optimal reference (1.000).

Please decide the claim wording for the deck; the video will use the same words. I am not picking one myself.
Until then the video's S2 shows the chart as the data stands, with neutral narration.
