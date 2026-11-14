"""A1-21 templated discovery rationales from engine truth.

A Narrator follows one playthrough and writes the NOTES / HYPOTHESIS fields of A3's harness
reply, phrased as discovery. It only ever refers to things the player can see (colour index
as shown in the frame, plus a shape word) and states an effect only after the player has seen
it happen. It never uses rule names.

    nar = Narrator(game)                    # engine Game, at the state the trajectory starts
    notes, hyp = nar.before(plan)           # before choosing the action at the current state
    game.step(action); nar.after(action, game)

A3's arena/dataset.py calls these in place of its own `_notes`, so the prompt format
(build_parts) stays A3's and train == inference.
"""
from __future__ import annotations

from ..core.game import Game
from .common import visible_roles

SHAPE = {"full": "solid square", "ring": "ring", "dot": "small dot", "cross": "plus sign", "x": "X mark",
         "corners": "corner-marked tile", "hbar": "horizontal bar", "vbar": "vertical bar",
         "checker": "checkered tile", "frame_dot": "framed dot", "bars": "barred tile",
         "diag": "striped tile", "diamond": "diamond", "half": "half-filled tile", "tri": "triangle",
         "arrow_up": "arrow tile", "arrow_down": "arrow tile", "arrow_left": "arrow tile",
         "arrow_right": "arrow tile"}
QUIET = {"floor", "wall", "player", "goal", "budget_bar", "budget_empty", "health", "stamina",
         "trail", "phase_open", "hole", "decoy_a", "decoy_b"}

# event -> (fact key, role that explains it, template); {o} = the object's description
FACTS = {
    "picked_key": ("key", "key", "Walking onto the {o} picks it up; it then shows in the top bar."),
    "opened_door": ("door", "door", "Walking into the {o} while carrying a picked-up item opens it and uses the item up."),
    "collected": ("gem", "gem", "Walking onto a {o} collects it (a pip in the top bar fills); the goal only counted after all were collected."),
    "pressed_plate": ("plate", "plate", "Stepping onto the {o} opens or closes the barriers of the same colour."),
    "pushed": ("block", "block", "Walking into the {o} pushes it one cell if the space behind it is free."),
    "hurt": ("hazard", "hazard", "Stepping onto a {o} costs one pip of the meter in the top bar; when it runs out the level is lost."),
    "refilled": ("refill", "refill", "Stepping onto the {o} refills the meter in the top bar."),
    "teleport": ("teleport", "teleporter", "Stepping onto a {o} moves me to the other {o}."),
    "floor_collapsed": ("crack", "cracked", "A {o} holds me once; after I leave it, it becomes a hole I can't enter."),
    "decoy": ("decoy", None, "Not every ring is the goal: one sent me back to the start. The real goal matches the colour shown in the top bar."),
    "rotated": ("rotate", "rotator", "Touching the {o} turns the whole board; my arrow actions still move me on screen."),
    "controls_changed": ("remap", "remapper", "Touching the {o} changes which way each arrow action moves me."),
    "walls_closed": ("phase", "phase_wall", "The {o} walls appear and disappear on their own as I take actions."),
    "walls_opened": ("phase", "phase_wall", "The {o} walls appear and disappear on their own as I take actions."),
}
SLIDE = ("ice", "ice", "Moving onto a {o} keeps me sliding the same way until something stops me.")
EXPLAINS = {"key": {"key"}, "door": {"door"}, "gem": {"gem"}, "plate": {"plate", "gate"}, "block": {"block"},
            "hazard": {"hazard"}, "refill": {"refill"}, "teleport": {"teleporter"}, "crack": {"cracked"},
            "decoy": {"decoy_a", "decoy_b"}, "rotate": {"rotator"}, "remap": {"remapper"},
            "phase": {"phase_wall"}, "ice": {"ice"}, "oneway": {"one_way"}, "twin": {"twin", "twin_goal"}}


def compress(path: list[str]) -> str:
    out, i = [], 0
    while i < len(path):
        j = i
        while j + 1 < len(path) and path[j + 1] == path[i]:
            j += 1
        out.append(f"{path[i]}x{j - i + 1}" if j > i else path[i])
        i = j + 1
    return " ".join(out)


class Narrator:
    def __init__(self, game: Game):
        self.g = game
        self.facts: dict[str, str] = {}
        self.order: list[str] = []
        self.moved = False
        self.bumped = False

    # -- descriptions ------------------------------------------------------------------------
    def obj(self, role: str) -> str:
        col, spr = self.g.skin[role]
        return f"colour-{col:x} {SHAPE.get(spr, 'tile')}"

    def _learn(self, key: str, text: str) -> None:
        if key not in self.facts:
            self.order.append(key)
        self.facts[key] = text

    def _untested(self) -> list[str]:
        """Visible objects whose effect the player has not seen yet."""
        g = self.g
        done = set().union(*(EXPLAINS.get(k, set()) for k in self.facts)) if self.facts else set()
        roles = {r for r, _ in visible_roles(g.level, g.state, g.skin).values()}
        return sorted(r for r in roles if r not in QUIET and r not in done)

    # -- per turn ----------------------------------------------------------------------------
    def before(self, plan: list[str], detour: str | None = None) -> tuple[str, str]:
        g = self.g
        t = g.truth()
        lvl = f"Level {t['level']} of {t['levels_total']}."
        if t["state"] == "GAME_OVER":
            return (f"{lvl} The level is lost (red pattern on the floor). RESET restarts it; I must avoid what caused it.",
                    "this attempt failed; restart the level and change the plan")
        known = [self.facts[k] for k in self.order][-6:]
        left = t["move_budget"] - t["moves_used"]
        notes = (f"{lvl} About {left} moves left on the bar. "
                 + (" ".join(known) + " " if known else "")
                 + (f"Last move {detour} did not go as planned, replanning. " if detour else "")
                 + (f"Plan ({len(plan)} moves): {compress(plan[:24])}{' ...' if len(plan) > 24 else ''}" if plan else ""))
        new = self._untested()
        if new:
            hyp = (f"there is a {self.obj(new[0])} here I have not figured out yet; "
                   "I will watch what changes when I interact with it or pass near it")
        elif t["level"] == 1 and not self.moved:
            hyp = "I am probably the solid square; I will move and see what responds"
        else:
            hyp = "reach the goal ring in as few moves as possible using what I have learned"
        return notes.strip(), hyp

    def after(self, action: str, game: Game | None = None) -> None:
        g = game or self.g
        self.g = g
        ev = list(g.events)
        if action.startswith("ACTION") and not self.moved and "bump" not in ev:
            self.moved = True
            self._learn("me", f"I am the {self.obj('player')}: ACTION1-4 move me up, down, left, right.")
            self._learn("bar", "The bar at the top shrinks with every action: it counts the moves I have left.")
        if "bump" in ev and not self.bumped:
            self.bumped = True
            self._learn("bump", "Walking into walls does nothing but still costs a move.")
        for e in ev:
            if e in FACTS:
                key, role, tpl = FACTS[e]
                self._learn(key, tpl.format(o=self.obj(role)) if role else tpl)
            elif e.startswith("slid:") and "ice" in g.skin:
                self._learn(SLIDE[0], SLIDE[2].format(o=self.obj("ice")))
        if action.startswith("ACTION") and "bump" not in ev:
            here = visible_roles(g.level, g.state, g.skin)
            if "twin" in g.level.rules and "twin" in g.skin:
                self._learn("twin", f"The {self.obj('twin')} moves whenever I move (mirrored); it has to reach a ring of its colour too.")
            if any(r == "one_way" for r, _ in here.values()) and "one_way" in g.level.rules:
                st = g.level.data.get("one_way", {}).get("tiles", [])
                if any(tuple(t[:2]) == g.state.pos for t in st):
                    self._learn("oneway", f"A {self.obj('one_way')} can only be entered moving the way its arrow points.")
        if "level_complete" in ev:
            self._learn("goal", f"Reaching the {self.obj('goal')} finishes a level; the next level is a new board.")
        if "level_lost" in ev:
            self._learn("lose", "Running out of moves or health ends the level; only RESET helps then.")
