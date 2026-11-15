"""Sample only the train split and build the project's existing h1 SFT bootcamp."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "arena" / "src"), str(ROOT / "engine" / "src")]

from arena.dataset import build
from engine import list_games, load_game


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=8)
    ap.add_argument("--recover", type=float, default=2)
    ap.add_argument("--gameover", type=float, default=1)
    ap.add_argument("--seed", type=int, default=20261115)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    metadata = list_games("train-v1")
    rng = random.Random(a.seed)
    chosen = sorted(rng.sample(metadata, min(a.games, len(metadata))), key=lambda x: x["game_id"])
    collection = ROOT / "data" / "collections" / "train-v1.json"
    games = [(m["game_id"], lambda gid=m["game_id"]: load_game(collection, gid)) for m in chosen]
    stats = build(games, Path(a.out), n_recover=a.recover, n_gameover=a.gameover, seed=a.seed)
    manifest = {"source": "train-v1", "game_count": len(chosen),
                "game_ids": [m["game_id"] for m in chosen], "dataset_seed": a.seed,
                "recover_per_game": a.recover, "gameover_per_game": a.gameover,
                "stats": dict(stats)}
    Path(a.out + ".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
