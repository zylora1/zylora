from __future__ import annotations

import json

from zylora_api.modules.templates.scaling import (
    SCALE_MILESTONES,
    assert_scale_quality,
    build_scaled_catalogue,
)


def main() -> None:
    reports = []
    for milestone in SCALE_MILESTONES:
        report = assert_scale_quality(build_scaled_catalogue(milestone))
        reports.append(
            {
                "count": report.count,
                "categories": report.categories,
                "archetypes": report.archetypes,
                "layouts": report.layouts,
                "page_counts": report.page_counts,
            }
        )
    print(json.dumps({"validated_batches": reports}, separators=(",", ":")))


if __name__ == "__main__":
    main()
