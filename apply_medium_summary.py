import sys

with open('live_sentinel.py', 'r') as f:
    content = f.read()

# STEP 1, 3B, 4, 5 — Tracker initialization and threading logic
imports_and_tracker = """
import threading
import atexit
import requests
import time

medium_incident_tracker = {}
medium_tracker_lock = threading.Lock()
MEDIUM_INCIDENT_TIMEOUT = 300

def _send_medium_summary(ip, incident):
    duration = int(time.time() - incident["start_time"])
    pf = incident["peak_features"]
    msg = (
        f"🟡 MEDIUM INCIDENT SUMMARY\\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\\n"
        f"Attacker IP : {ip}\\n"
        f"Duration    : {duration}s\\n"
        f"Events      : {incident['event_count']} Medium-tier\\n"
        f"Peak Score  : {incident['peak_score']:.3f}\\n"
        f"Top Signals : failed_logins={pf.get('failed_logins')}, "
        f"cpu_usage={pf.get('cpu_usage')}, "
        f"ehr_access={pf.get('ehr_access_per_hour')}\\n"
        f"Actions     : {', '.join(incident['actions'])}\\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\\n"
        f"✅ Contained autonomously. No action required."
    )
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        logger.warning("MEDIUM SUMMARY SUPPRESSED: no bot token/chat_id")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=10
        )
        logger.info(f"[MEDIUM SUMMARY SENT] IP={ip} events={incident['event_count']} peak={incident['peak_score']:.3f}")
    except Exception as e:
        logger.error(f"Failed to send Medium summary: {e}")

def _medium_timeout_watcher():
    while True:
        time.sleep(30)
        now = time.time()
        with medium_tracker_lock:
            expired = [
                ip for ip, t in medium_incident_tracker.items()
                if now - t["start_time"] > MEDIUM_INCIDENT_TIMEOUT
            ]
            for ip in expired:
                incident = medium_incident_tracker.pop(ip)
                threading.Thread(
                    target=_send_medium_summary,
                    args=(ip, incident),
                    daemon=True
                ).start()

threading.Thread(target=_medium_timeout_watcher, daemon=True).start()

def _flush_medium_incidents():
    with medium_tracker_lock:
        for ip, incident in medium_incident_tracker.items():
            _send_medium_summary(ip, incident)
atexit.register(_flush_medium_incidents)

# Cryptographic Audit Ledger"""

if "medium_incident_tracker = {}" not in content:
    content = content.replace("# Cryptographic Audit Ledger", imports_and_tracker)

# STEP 3A — PATH A: Low tier event clears open Medium incident
low_tier_logic = """            if result['tier'] == 'Low':
                with medium_tracker_lock:
                    if ip in medium_incident_tracker:
                        _send_medium_summary(ip, medium_incident_tracker.pop(ip))
                responder_res = respond(result, ip_address=ip, telegram=False)"""
content = content.replace("if result['tier'] == 'Low':\n                responder_res = respond(result, ip_address=ip, telegram=False)", low_tier_logic)

# STEP 2 — PATH C: Medium tier tracking
medium_tier_logic = """            elif result['tier'] == 'Medium':
                with medium_tracker_lock:
                    if ip not in medium_incident_tracker:
                        medium_incident_tracker[ip] = {
                            "start_time": time.time(),
                            "peak_score": result['raw_score'],
                            "event_count": 1,
                            "peak_features": features,
                            "actions": ["Account locked", "IP throttled"]
                        }
                    else:
                        t = medium_incident_tracker[ip]
                        t["event_count"] += 1
                        if result['raw_score'] > t["peak_score"]:
                            t["peak_score"] = result['raw_score']
                            t["peak_features"] = features
                responder_res = respond(result, ip_address=ip, telegram=False)"""
content = content.replace("elif result['tier'] == 'Medium':\n                responder_res = respond(result, ip_address=ip, telegram=False)", medium_tier_logic)


with open('live_sentinel.py', 'w') as f:
    f.write(content)
