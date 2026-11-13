"""Level + state -> 64x64 frame (list of 64 hex strings). No text, no numbers (§4.1)."""
from __future__ import annotations

from ..core.level import Level, State
from .. import components as comps
from .canvas import SIZE, Canvas

from .colors import LOSE_COLOR, PIP_CURRENT, PIP_DONE, PIP_TODO, WIN_COLOR


def _budget_bar(cv: Canvas, level: Level, state: State) -> None:
    if level.move_budget <= 0:
        return
    left = max(0, level.move_budget - state.moves)
    n = (left * SIZE + level.move_budget - 1) // level.move_budget  # ceil: 1 move left -> >=1 px
    cv.rect(0, 0, SIZE, 2, cv.color("budget_empty"))
    cv.rect(0, 0, n, 2, cv.color("budget_bar"))


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

    cv.set_grid(level.w, level.h)
    for c in comps.active(level):
        c.draw(level, state, cv)
    cv.cell(state.pos, "player")
    _budget_bar(cv, level, state)
    x = _pips(cv, level_idx, levels_total, False)
    _hud_items(cv, level, state, x)

    if status == "GAME_OVER":
        floor = skin["floor"][0]
        for y in range(6, SIZE):
            row = cv.px[y]
            for xx in range(SIZE):
                if row[xx] == floor and (xx + y) % 2 == 0:
                    row[xx] = LOSE_COLOR
    return cv.to_hex()
