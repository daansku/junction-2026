from __future__ import annotations

from .base import Component
from . import register
from ..render import colors as C


@register
class Walls(Component):
    name = "walls"
    always_on = True
    layer = 10
    roles = {"wall": (C.WALL, "full")}

    def blocks(self, level, state, pos, d):
        return pos in level.walls

    def blocks_object(self, level, state, pos):
        return pos in level.walls

    def draw(self, level, state, cv):
        for p in level.walls:
            cv.cell(p, "wall")
