"""Palette indices by name (contracts/palette.json). Use these, never raw numbers."""
BLACK, BLUE, RED, GREEN, YELLOW, GREY, MAGENTA, ORANGE = 0, 1, 2, 3, 4, 5, 6, 7
AZURE, MAROON, WHITE, DARK_GREY, VIOLET, TEAL, LIME, BROWN = 8, 9, 10, 11, 12, 13, 14, 15

FLOOR = BLACK
WALL = GREY
BUDGET_BAR, BUDGET_EMPTY = YELLOW, DARK_GREY
WIN_COLOR, LOSE_COLOR = GREEN, RED
PIP_DONE, PIP_CURRENT, PIP_TODO = GREEN, WHITE, DARK_GREY

# colours a component may be skinned with: everything except structural ones above
OBJECT_POOL = [BLUE, GREEN, MAGENTA, ORANGE, AZURE, WHITE, VIOLET, TEAL, LIME, BROWN, MAROON]
