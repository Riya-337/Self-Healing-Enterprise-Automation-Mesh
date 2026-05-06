import os
import re

# =================================================================
# BUG 1 & BUG 4: HIGH-TIER COOLDOWN & RISK SCORE (live_sentinel.py)
# =================================================================
with open('live_sentinel.py', 'r') as f:
    ls_content = f.read()

# Add to module top
cooldown_globals = """
alerted_ips = {}          # ip -> last_alert_unix_timestamp
ALERT_COOLDOWN_SECS = 300 # 5 minutes per IP

def compute_risk_score(features):
    \"\"\"Continuous 0.0-1.0 risk score from raw feature values.
    Independent of ML classification — human-readable intensity.\"\"\"
    return round(
        0.30 * min(features.get("failed_logins", 0) / 10.0, 1.0) +
        0.30 * min(features.get("cpu_usage", 0.0), 1.0) +
        0.20 * min(features.get("ehr_access_per_hour", 0) / 20.0, 1.0) +
        0.20 * min(features.get("request_rate", 0) / 12.0, 1.0),
        3
    )
"""

if "alerted_ips =" not in ls_content:
    ls_content = ls_content.replace("session_start_time = None", cooldown_globals + "\nsession_start_time = None")

# Apply compute_risk_score logic and High Tier Cooldown
# Locate the block where score_event is called
score_call = "result = score_event(features)"
new_score_call = """result = score_event(features)
            
            risk_score = compute_risk_score(features)
            ml_score = result['raw_score']
            result['raw_score'] = risk_score
            logger.info(f"Tier={result['tier']} | ML_prob={ml_score:.3f} | Risk={risk_score:.3f}")"""
if "compute_risk_score(features)" not in ls_content:
    ls_content = ls_content.replace(score_call, new_score_call)

# Apply Cooldown in High Tier handling
high_tier_old = """            else:
                responder_res = respond(result, ip_address=ip, telegram=True)"""
high_tier_new = """            else:
                _now = time.time()
                _last = alerted_ips.get(ip, 0)
                if _now - _last < ALERT_COOLDOWN_SECS:
                    logger.info(f"[COOLDOWN] High alert suppressed for {ip} — {int(ALERT_COOLDOWN_SECS-(_now-_last))}s remaining")
                    result['dedup_suppress'] = True
                else:
                    alerted_ips[ip] = _now
                responder_res = respond(result, ip_address=ip, telegram=True)"""
if "alerted_ips.get(ip, 0)" not in ls_content:
    ls_content = ls_content.replace(high_tier_old, high_tier_new)

with open('live_sentinel.py', 'w') as f:
    f.write(ls_content)


# =================================================================
# BUG 3: RANDOM IPs IN EXFILTRATION.PY
# =================================================================
with open('attack_scripts/exfiltration.py', 'r') as f:
    ex_content = f.read()

random_ip_code = """from faker import Faker
_faker = Faker()
ATTACKER_IP_LOW    = _faker.ipv4_private()
ATTACKER_IP_MEDIUM = _faker.ipv4_private()
ATTACKER_IP_HIGH   = _faker.ipv4_private()

print(f"[*] Simulated IPs — Low:{ATTACKER_IP_LOW} Medium:{ATTACKER_IP_MEDIUM} High:{ATTACKER_IP_HIGH}")

log_file ="""
if "ATTACKER_IP_LOW" not in ex_content:
    ex_content = ex_content.replace("log_file =", random_ip_code)

old_source_ip = "\"source_ip\": \"10.0.0.47\" if \"Phase 1\" in phase[\"name\"] else (\"10.0.0.83\" if \"Phase 2\" in phase[\"name\"] else (\"10.0.0.47\" if event_idx % 2 == 0 else \"10.0.0.83\"))"
new_source_ip = "\"source_ip\": ATTACKER_IP_LOW if \"Phase 1\" in phase[\"name\"] else (ATTACKER_IP_MEDIUM if \"Phase 2\" in phase[\"name\"] else (ATTACKER_IP_HIGH if event_idx % 2 == 0 else ATTACKER_IP_MEDIUM))"

if "ATTACKER_IP_LOW if" not in ex_content:
    ex_content = ex_content.replace(old_source_ip, new_source_ip)

with open('attack_scripts/exfiltration.py', 'w') as f:
    f.write(ex_content)
