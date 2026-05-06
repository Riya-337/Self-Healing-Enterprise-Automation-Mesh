from scoring_matrix import score_event
import scoring_matrix
features_med = {
    'failed_logins': 4,
    'cpu_usage': 0.45,
    'ehr_access_per_hour': 8,
    'data_export_volume_kb': 150000 / 1024,
    'attack_type': 'normal',
    'asset_type': 'ehr'
}
scoring_matrix.velocity_buffer = [0.1]*5
res = score_event(features_med)
print(f"Tier: {res['tier']}, Score: {res['raw_score']}")
