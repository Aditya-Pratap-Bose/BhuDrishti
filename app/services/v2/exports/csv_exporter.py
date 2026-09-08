"""
app/services/v2/exports/csv_exporter.py
---------------------------------------
Attribute tabular export utility for cadastral plots and revenue records.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any


def export_to_csv(
    features: list[dict[str, Any]],
    output_path: str | Path | None = None,
) -> str:
    """Export properties from GeoJSON features to a CSV string/file."""
    if not features:
        return ""

    # Collect all unique property keys
    headers = set()
    for feat in features:
        props = feat.get("properties", {})
        headers.update(props.keys())

    sorted_headers = sorted(list(headers))
    if "ulpin" in sorted_headers:
        sorted_headers.remove("ulpin")
        sorted_headers.insert(0, "ulpin")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=sorted_headers, lineterminator="\n")
    writer.writeheader()

    for feat in features:
        props = feat.get("properties", {})
        row = {k: props.get(k, "") for k in sorted_headers}
        writer.writerow(row)

    csv_content = output.getvalue()

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            f.write(csv_content)

    return csv_content
