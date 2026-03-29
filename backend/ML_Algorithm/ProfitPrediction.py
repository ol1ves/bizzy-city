import joblib
import numpy as np
import pandas as pd

NYC_INCOMES = {
    '10032': 27257, '10033': 27257, '10040': 27257, '10034': 27257, '10463': 27257,
    '10031': 26694, '10027': 26694,
    '10030': 34463, '10037': 34463, '10039': 34463,
    '10029': 22975, '10035': 22975,
    '10023': 85724, '10024': 85724, '10025': 85724, '10069': 85724,
    '10021': 87724, '10028': 87724, '10044': 87724, '10065': 87724, '10075': 87724, '10128': 87724,
    '10001': 77071, '10011': 77071, '10018': 77071, '10019': 77071, '10020': 77071, '10036': 77071,
    '10010': 83546, '10016': 83546, '10017': 83546, '10022': 83546,
    '10004': 93990, '10005': 93990, '10006': 93990, '10007': 93990, '10012': 93990, '10013': 93990, '10014': 93990, '10280': 93990,
    '10002': 23393, '10003': 23393, '10009': 23393
}

# ── Industry Profiles (Years 1-5, then Year 10) ─────────────────────────────
INDUSTRY_PROFILES = {
    'accommodation_and_food_services': {
        'label':    'accommodation_and_food_services',
        'years':    [1, 2, 3, 4, 5, 10],
        'rate':     [0.829, 0.724, 0.648, 0.587, 0.536, 0.377],
        'avg_emp':  [14.0, 15.1, 16.1, 17.0, 17.8, 21.0],
        'friction': 1.1,
    },
    'health_care_and_social_assistance': {
        'label':    'health_care_and_social_assistance',
        'years':    [1, 2, 3, 4, 5, 10],
        'rate':     [0.827, 0.732, 0.661, 0.603, 0.555, 0.395],
        'avg_emp':  [4.8, 5.7, 6.4, 7.1, 7.8, 11.2],
        'friction': 0.7,
    },
    'retail_trade': {
        'label':    'retail_trade',
        'years':    [1, 2, 3, 4, 5, 10],
        'rate':     [0.846, 0.746, 0.670, 0.610, 0.558, 0.391],
        'avg_emp':  [8.5, 9.6, 10.5, 11.3, 12.1, 15.3],
        'friction': 1.3,
    },
    'arts_entertainment_and_recreation': {
        'label':    'arts_entertainment_and_recreation',
        'years':    [1, 2, 3, 4, 5, 10],
        'rate':     [0.813, 0.706, 0.624, 0.559, 0.505, 0.327],
        'avg_emp':  [9.1, 10.3, 11.3, 12.1, 13.0, 16.1],
        'friction': 1.2,
    },
    'real_estate_and_rental_and_leasing': {
        'label':    'real_estate_and_rental_and_leasing',
        'years':    [1, 2, 3, 4, 5, 10],
        'rate':     [0.832, 0.733, 0.658, 0.596, 0.547, 0.370],
        'avg_emp':  [4.1, 4.4, 4.8, 5.1, 5.4, 6.4],
        'friction': 2.0,
    },
    'other_services': {
        'label':    'other_services',
        'years':    [1, 2, 3, 4, 5, 10],
        'rate':     [0.827, 0.731, 0.657, 0.596, 0.546, 0.376],
        'avg_emp':  [4.5, 4.9, 5.3, 5.6, 5.9, 7.0],
        'friction': 1.0,
    },
}
def get_advanced_features(zip_code, foot_traffic, industry_label):
    base_income = NYC_INCOMES.get(str(zip_code), 35000)
    industry_obj = INDUSTRY_PROFILES[industry_label]
    friction = industry_obj.get('friction', 1.0)
    if base_income > 85000: tier=3
    elif base_income > 70000: tier=2
    elif base_income > 30000: tier=1
    else: tier=0
    return {
        'income_proxy': base_income,
        'traffic_volume': foot_traffic,
        'neighborhood_tier': tier,
        'spend_capacity': foot_traffic * (base_income/100_000),
        'traffic_efficiency': np.log1p(foot_traffic)/friction,
        'industry_friction': friction
    }

def compute_competition_index(comps, my_traffic):
    if not comps: return 0.0
    count_factor = (len(comps)/20)**1.5
    avg_comp_traffic = np.mean([c['foot_traffic'] for c in comps])
    traffic_factor = np.clip(np.log1p(avg_comp_traffic/(my_traffic+1)*3)/1.5, 0, 1)
    avg_age = np.mean([c['years_open'] for c in comps])
    age_factor = np.log1p(avg_age)/np.log1p(20)
    return np.clip(0.5*count_factor + 0.3*traffic_factor + 0.2*age_factor + 0.5*count_factor*traffic_factor, 0, 1)

# Load trained model
final_model = joblib.load("IEEEHackathon_Model.pkl")

def predict_lot_success_ml(zip_code, foot_traffic, industry_label, age_idx, nearby_competitors):
    feats = get_advanced_features(zip_code, foot_traffic, industry_label)
    industries = list(INDUSTRY_PROFILES.keys())
    comp_count = len(nearby_competitors) if nearby_competitors else 0
    ages = [c['years_open'] for c in nearby_competitors] if nearby_competitors else []
    young_ratio = sum(a<3 for a in ages)/len(ages) if ages else 0
    old_ratio = sum(a>10 for a in ages)/len(ages) if ages else 0
    avg_comp_age = np.mean(ages) if ages else 0
    input_df = pd.DataFrame([{
        'income_proxy': feats['income_proxy'],
        'traffic_volume': feats['traffic_volume'],
        'neighborhood_tier': feats['neighborhood_tier'],
        'spend_capacity': feats['spend_capacity'],
        'traffic_efficiency': feats['traffic_efficiency'],
        'industry_friction': feats['industry_friction'],
        'industry_idx': industries.index(industry_label),
        'age_idx': age_idx,
        'comp_count': comp_count,
        'avg_comp_age': avg_comp_age,
        'young_comp_ratio': young_ratio,
        'old_comp_ratio': old_ratio
    }])
    score = final_model.predict(input_df)[0]
    return np.clip(score, 0, 100)

def calculate_average_traffic(traffic_data: dict) -> float:
    """Weighted daily average: 5 weekdays + 2 weekend days."""
    weekday_total = (traffic_data['weekday_am'] +
                     traffic_data['weekday_mid'] +
                     traffic_data['weekday_pm'])
    weekend_total = (traffic_data['weekend_am'] +
                     traffic_data['weekend_mid'] +
                     traffic_data['weekend_pm'])
    return round(((weekday_total * 5) + (weekend_total * 2)) / 7, 2)