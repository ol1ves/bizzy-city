import pandas as pd
from .pckl import get_traffic_by_coords

TIME_SLOT_LABELS = {
    "predwkdyAM": "Weekday AM (8-9)",
    "predwkdyMD": "Weekday Midday (12:30-1:30)",
    "predwkdyPM": "Weekday PM (5-6)",
    "predwkndAM": "Weekend AM (8-9)",
    "predwkndMD": "Weekend Midday (12:30-1:30)",
    "predwkndPM": "Weekend PM (5-6)",
}


def get_foot_traffic_analysis(lat: float, lng: float) -> str:
    """Estimate pedestrian foot traffic and return a formatted text summary."""
    result = get_traffic_by_coords(lat, lng)

    if isinstance(result, str):
        return result

    if not isinstance(result, pd.DataFrame) or result.empty:
        return "No foot traffic data available for these coordinates."

    row = result.iloc[0]
    lines = []
    for col, label in TIME_SLOT_LABELS.items():
        val = row.get(col)
        if val is not None and pd.notna(val):
            lines.append(f"{label}: {int(val):,}")
        else:
            lines.append(f"{label}: N/A")

    dist = row.get("dist_meters")
    if dist is not None and pd.notna(dist):
        lines.append(f"Nearest sidewalk segment: {dist:.1f}m away")

    return "\n".join(lines)
