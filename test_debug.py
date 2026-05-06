from scoring_matrix import score_event
features_med = {
    'failed_logins': 4,
    'cpu_usage': 0.45,
    'ehr_access_per_hour': 8,
    'data_export_volume_kb': 150000 / 1024,
    'attack_type': 'normal',
    'asset_type': 'ehr'
}
res = score_event(features_med)
print(f"Tier: {res['tier']}, Score: {res['raw_score']}")
