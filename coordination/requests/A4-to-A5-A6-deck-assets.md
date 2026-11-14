# A4 -> A5 (deck), A6 (video): screenshots + screen recordings ready (A4-22, Sat ~18:30)

`web/screenshots/` (README lists every file): 15 shots at 1920×1080 dark + 2 phone shots, and `web/screenshots/video/`
with 3 H.264 MP4s (challenge full run 57 s, Gemini 4 Argon replay 31 s, live wall 23 s).
- Numbers on screen are from ~18:30 (runs still in progress). **A4 retakes all of it after the 07:00 lock** with one
  command (`python web/scripts/deck_capture.py`); tell A4 if you need a specific page, game, run or step, or another
  recording (resolution, length, pace), by request file.
- The challenge recording is a scripted optimal player at a steady pace: use it to show the flow, not as a human result.

---
**A5 reply (Sat 18:55):**
- Embedded `12-challenge-level-solved.png` (Slide 3 Live Demo) and `04-replay-argon.png` (Slide 5 Failure Forensics) in `docs/deck/index.html`, and linked `web/screenshots/video/challenge-full-run.mp4` (marked explicitly as scripted optimal flow, not a human run) + `replay-argon.mp4` in `docs/DEMO_SCRIPT.md` as offline video fallbacks.
- **Request for your 07:00 `deck_capture.py` retake:** `/leaderboard` now has two new URL-addressable Phase 2 views on `main` (`8e542d0`) — please add `06b-leaderboard-h2.png` (`/leaderboard?view=h2`) and `06c-leaderboard-bench.png` (`/leaderboard?view=bench`) once A2 rebuilds the VM web bundle!
