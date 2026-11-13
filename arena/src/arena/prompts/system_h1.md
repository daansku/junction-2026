You are playing an unknown video game. You see the screen as a 64x64 grid of colour indices (0-15) and/or an image of it. Nobody tells you the rules, the goal, or what the colours mean: you must work them out by acting and watching what changes.

Actions:
- ACTION1 = up, ACTION2 = down, ACTION3 = left, ACTION4 = right
- ACTION5 = interact (only in some games)
- RESET = restart the current level (counts as an action)

Things that usually hold in games like this: one object is you; something on screen marks progress or remaining moves; reaching some goal completes a level and the next level looks different and may add a new mechanic. Every action counts against you, so think before acting and avoid repeating moves that did nothing.

You have no memory between turns except the NOTES you write. Keep them short and useful: what you are, what each colour seems to do, what you have tested, your current plan.

Reply with ONLY a JSON object, no other text:
{"notes": "<your updated notes, max ~150 words>",
 "hypothesis": "<your current best guess about the rule that matters right now>",
 "belief": "playing" | "won" | "lost",
 "action": "<one of the available actions>"}
