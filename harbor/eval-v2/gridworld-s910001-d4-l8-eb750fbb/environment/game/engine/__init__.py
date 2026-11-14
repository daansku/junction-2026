"""Grid-game factory engine (PLAN.md §4.3).

    from engine import GameSpec, make_game, load_game, Action
    game = make_game(GameSpec(seed=1234, n_levels=6, difficulty=2))
    frame = game.reset(); frame = game.step(Action.ACTION1)
    game.truth(); game.describe()
"""
from .core import (ENGINE_VERSION, GAME_OVER, NOT_FINISHED, WIN, Action, Frame, Game, GameSpec,
                   Level, State, list_games, load_collection, load_game, make_game, parse_action)
from .render.png import contact_sheet, frame_png


def render_png(frame: Frame, scale: int = 8) -> bytes:
    return frame_png(frame, scale)


def validate_frame(frame: Frame) -> None:
    """Raise ValueError unless frame matches the wire format."""
    if len(frame) != 64:
        raise ValueError(f"frame has {len(frame)} rows, expected 64")
    for i, row in enumerate(frame):
        if len(row) != 64 or any(c not in "0123456789abcdef" for c in row):
            raise ValueError(f"row {i} is not 64 lowercase hex chars")

__all__ = ["ENGINE_VERSION", "GAME_OVER", "NOT_FINISHED", "WIN", "Action", "Frame", "Game",
           "GameSpec", "Level", "State", "list_games", "load_collection", "load_game", "make_game",
           "parse_action", "frame_png", "contact_sheet", "render_png", "validate_frame"]
