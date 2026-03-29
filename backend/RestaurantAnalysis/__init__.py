from .FullAPIPull import scrape_area, opportunity_score, enrich_and_rank


def get_restaurant_analysis(lat: float, lng: float) -> str:
    """Analyze nearby restaurant categories and return a ranked text summary."""
    google_data, total_found = scrape_area(lat, lng)
    initial_ranked = opportunity_score(google_data)
    final_ranked = enrich_and_rank(initial_ranked, google_data, total_found, top_n=15)

    lines = []
    for i, res in enumerate(final_ranked, 1):
        pain = "LOW"
        if res['y']:
            if res['y'].get('complaint_rate', 0) > 0.18:
                pain = "HIGH"
            elif res['y'].get('wait_rate', 0) > 0.12:
                pain = "MED"
        lines.append(
            f"{i}. {res['cat']} | Score: {res['score']} "
            f"| Share: {res['share']:.1%} "
            f"| Pain: {pain}"
        )
    return "\n".join(lines)
