import time
from .RetailAPIPull import (
    CATEGORIES,
    search_nearby_retail,
    calculate_hub_aware_opportunity,
)


def get_retail_analysis(lat: float, lng: float) -> str:
    """Scan nearby retail categories and return a ranked text summary."""
    raw_market_data = {}
    for category in CATEGORIES:
        raw_market_data[category] = search_nearby_retail(lat, lng, category)
        time.sleep(0.05)

    rankings = calculate_hub_aware_opportunity(raw_market_data)
    if not rankings:
        return ""

    lines = []
    for i, res in enumerate(rankings[:25], 1):
        pain = "HIGH" if res['friction'] > 0.2 else "MED" if res['friction'] > 0.05 else "LOW"
        lines.append(
            f"{i}. {res['category']} | Score: {res['score']:.1f} "
            f"| Share: {res['share']:.1%} | Pain: {pain}"
        )
    return "\n".join(lines)
