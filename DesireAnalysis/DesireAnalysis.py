# desire_service.py
from DesireAnalysis.FullAPIPull import scrape_area, opportunity_score, enrich_and_rank

def get_desire_analysis(lat: float, lng: float) -> str:
    google_data, total_found = scrape_area(lat, lng)
    initial_ranked = opportunity_score(google_data)
    final_ranked = enrich_and_rank(initial_ranked, google_data, total_found, top_n=15)
    
    # Format to the text string your LLM will consume
    lines = []
    for i, res in enumerate(final_ranked, 1):
        pains = []
        if res['y']:
            if res['y']['complaint_rate'] > 0.18: pains.append("Poor Quality")
            if res['y']['wait_rate'] > 0.12: pains.append("Wait Times")
        lines.append(f"{i}. {res['cat']} | Score: {res['score']} | Share: {res['share']:.1%} | Pains: {', '.join(pains) or 'None'}")
    return "\n".join(lines)