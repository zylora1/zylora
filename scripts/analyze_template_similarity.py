"""Flag perceptually similar Template screenshots for human visual review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from PIL import Image


def difference_hash(path: Path, *, width: int = 16, height: int = 16) -> int:
    with Image.open(path) as source:
        image = source.convert("L").resize((width + 1, height), Image.Resampling.LANCZOS)
        pixels = cast(list[int], image.get_flattened_data())
    value = 0
    for row in range(height):
        offset = row * (width + 1)
        for column in range(width):
            value = (value << 1) | int(pixels[offset + column] > pixels[offset + column + 1])
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/template-visual-audit/manifest.json"),
    )
    parser.add_argument("--distance", type=int, default=6)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = manifest["records"]
    hashes = [(record, difference_hash(Path(record["desktop"]))) for record in records]
    suspicious: list[dict[str, Any]] = []
    for left_index, (left, left_hash) in enumerate(hashes):
        for right, right_hash in hashes[left_index + 1 :]:
            distance = (left_hash ^ right_hash).bit_count()
            if distance <= args.distance:
                suspicious.append(
                    {
                        "left": left["slug"],
                        "right": right["slug"],
                        "distance": distance,
                        "same_family": left["family"] == right["family"],
                        "same_industry": left["category"] == right["category"],
                    }
                )
    suspicious.sort(key=lambda pair: (pair["distance"], pair["left"], pair["right"]))
    report = {
        "algorithm": "16x16 difference hash",
        "distance_threshold": args.distance,
        "templates": len(records),
        "pairs_compared": len(records) * (len(records) - 1) // 2,
        "suspicious_pairs": suspicious,
    }
    target = args.manifest.with_name("similarity-report.json")
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Compared {report['pairs_compared']} screenshot pairs; "
        f"flagged {len(suspicious)} for visual review: {target}"
    )


if __name__ == "__main__":
    main()
