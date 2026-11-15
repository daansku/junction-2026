"""Level + state -> 64x64 frame (list of 64 hex strings). No text, no numbers (§4.1)."""
from __future__ import annotations

from ..core.level import Level, State
from .. import components as comps
from .canvas import HUD_ROWS, SIZE, Canvas

from .colors import LOSE_COLOR, PIP_CURRENT, PIP_DONE, PIP_TODO, WIN_COLOR


def _budget_bar(cv: Canvas, level: Level, state: State) -> None:
    if level.move_budget <= 0:
        return
    left = max(0, level.move_budget - state.moves)
    n = (left * SIZE + level.move_budget - 1) // level.move_budget  # ceil: 1 move left -> >=1 px
    cv.rect(0, 0, SIZE, 2, cv.color("budget_empty"))
    cv.rect(0, 0, n, 2, cv.color("budget_bar"))


def _recolor(cv: Canvas, m: list[int], y0: int, y1: int, x0: int = 0) -> None:
    for y in range(y0, min(SIZE, y1)):
        row = cv.px[y]
        for x in range(x0, SIZE):
            row[x] = m[row[x]]


def _fog(cv: Canvas, level: Level, pos: tuple[int, int], radius: int, fog: int) -> None:
    """Grid cells farther than `radius` (Chebyshev) from the player show only the fog colour."""
    cs = cv.cs
    for y in range(level.h):
        for x in range(level.w):
            if max(abs(x - pos[0]), abs(y - pos[1])) > radius:
                sx, sy = cv._xf(x, y, cv.lw, cv.lh)
                cv.rect(cv.ox + sx * cs, cv.oy + sy * cs, cs, cs, fog)


def _pips(cv: Canvas, level_idx: int, levels_total: int, won_all: bool) -> int:
    x = 0
    for i in range(levels_total):
        col = PIP_DONE if (i < level_idx or won_all) else PIP_CURRENT if i == level_idx else PIP_TODO
        cv.rect(x, 3, 2, 2, col)
        x += 3
    return x


def _hud_items(cv: Canvas, level: Level, state: State, x: int) -> None:
    x += 3
    for c in comps.active(level):
        for role, value, vmax in c.hud(level, state):
            col = cv.color(role)
            if vmax > 6:  # long meters: 1 px per unit, dim tick for spent units
                if x + vmax > SIZE:
                    return
                cv.rect(x, 3, vmax, 1, col)
                cv.rect(x, 4, value, 1, col)
                x += vmax + 2
                continue
            for i in range(vmax):
                if x + 2 > SIZE:
                    return
                if i < value:
                    cv.rect(x, 3, 2, 2, col)
                else:
                    cv.put(x, 4, col)
                x += 3
            x += 2


def render(level: Level, state: State, skin: dict[str, tuple[int, str]], level_idx: int,
           levels_total: int, status: str = "NOT_FINISHED") -> list[str]:
    """status: NOT_FINISHED | GAME_OVER (this level lost) | WIN (all levels done)."""
    cv = Canvas(skin, fill=skin["floor"][0])
    if status == "WIN":
        cv.rect(0, 0, SIZE, SIZE, WIN_COLOR)
        cv.rect(4, 10, SIZE - 8, SIZE - 14, skin["floor"][0])
        for i in range(0, SIZE - 8, 4):  # checker band says "done"
            cv.rect(4 + i, 30 + (i // 4 % 2) * 2, 2, 2, WIN_COLOR)
        _pips(cv, levels_total, levels_total, True)
        return cv.to_hex()

    cv.set_grid(level.w, level.h, rot=int(state.c.get("rotation", 0)),
                stable="rotation" in level.rules)
    for c in comps.active(level):
        c.draw(level, state, cv)
    cv.cell(state.pos, "player")
    view = level.data.get("view") or {}  # eval-v6 (generator/view.py): what the player sees, never the rules
    if view.get("recolor"):
        _recolor(cv, view["recolor"], HUD_ROWS, SIZE)
    if view.get("radius") is not None and not (view.get("glimpse") and state.moves == 0):
        _fog(cv, level, state.pos, int(view["radius"]), int(view["fog"]))
    _budget_bar(cv, level, state)
    x = _pips(cv, level_idx, levels_total, False)
    _hud_items(cv, level, state, x)
    if view.get("recolor"):  # held items in the HUD match the recoloured objects
        _recolor(cv, view["recolor"], 3, HUD_ROWS, x + 1)

    if status == "GAME_OVER":
        floor = skin["floor"][0]
        for y in range(6, SIZE):
            row = cv.px[y]
            for xx in range(SIZE):
                if row[xx] == floor and (xx + y) % 2 == 0:
                    row[xx] = LOSE_COLOR
    return cv.to_hex()
