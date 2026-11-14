# Play an unknown game

An MCP server named `game` (http://localhost:8000/mcp) runs a video game you have never seen. It has two tools:

- `observe()` shows the current screen (free).
- `act(action, note?)` takes one action and shows the new screen. Actions: `ACTION1` up, `ACTION2` down,
  `ACTION3` left, `ACTION4` right, `ACTION5` interact (only in games that list it as available), `RESET` restart the current level.

The screen is a 64x64 image, also given as a text grid (one hex digit 0-f per cell = colour index, row 0 at the top).
Nobody tells you the goal, the rules or what the colours mean: work them out by acting and watching what changes.
The game has several levels; later levels may add new mechanics.

**Goal:** finish as many levels as you can, using as few actions as possible. Every action (including RESET) counts
against your score; looking with `observe()` is free. When you have finished the game, or are certain you cannot
make more progress, stop. Do not look for the score anywhere else: only playing through the `game` tools counts.
