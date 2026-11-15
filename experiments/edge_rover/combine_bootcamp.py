"""Combine mixed recovery examples and broader train-v1 optimal demonstrations."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mixed", required=True, help="optimal + recovery + game-over subset")
    ap.add_argument("--broad", required=True, help="broader optimal-only train-v1 subset")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    mixed, broad = rows(Path(a.mixed)), rows(Path(a.broad))
    mixed_games = {r["meta"]["game_id"] for r in mixed}
    broad_games = {r["meta"]["game_id"] for r in broad}
    if mixed_games & broad_games:
        raise SystemExit(f"refusing overlapping source games: {sorted(mixed_games & broad_games)}")
    all_rows = mixed + broad
    out = Path(a.out)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows), encoding="utf-8")
    manifest = {"source": "train-v1 only", "mixed_source": str(Path(a.mixed).name),
                "broad_source": str(Path(a.broad).name), "examples": len(all_rows),
                "mixed_examples": len(mixed), "broad_examples": len(broad),
                "game_count": len(mixed_games | broad_games),
                "mixed_games": sorted(mixed_games), "broad_games": sorted(broad_games),
                "kinds": dict(Counter(r["meta"]["kind"] for r in all_rows))}
    Path(str(out) + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("examples", "game_count", "kinds")}))


if __name__ == "__main__":
    main()
