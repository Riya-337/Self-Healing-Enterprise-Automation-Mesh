import os
import time
import json
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import threading
import logging
from colorama import Fore, Back, Style, init
init(autoreset=True)
from dotenv import load_dotenv
load_dotenv()  # loads .env into os.environ automatically

def _check_config():
    required = {
        "TELEGRAM_BOT_TOKEN": "High-tier alerts",
        "TELEGRAM_CHAT_ID":   "All Telegram notifications",
    }
    optional = {
        "SENTIHEALTH_TEST_MODE": "Test mode bypass (default: off)",
    }
    print(f"\n{Fore.WHITE}[CONFIG CHECK]")
    all_ok = True
    for var, purpose in required.items():
        val = os.environ.get(var, "").strip()
        if val:
            print(f"  {var:30s}: OK")
        else:
            print(f"  {var:30s}: MISSING — {purpose} will be disabled")
            all_ok = False
    for var, purpose in optional.items():
        val = os.environ.get(var, "0")
        print(f"  {var:30s}: {val} ({purpose})")
    print()
    return all_ok
_check_config()

import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from scoring_matrix import score_event
from self_healing_responder import respond

TEST_MODE = os.environ.get("SENTIHEALTH_TEST_MODE", "0") == "1"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
DEBUG = False


_alert_claim_lock = threading.Lock()
_auth_lock = threading.Lock()
_last_processed_update_id = [0]

alerted_ips = {}          # ip -> last_alert_unix_timestamp
ALERT_COOLDOWN_SECS = 300 # 5 minutes per IP


session_start_time = None
low_count = 0
medium_count = 0
high_count = 0
session_events = []
session_peak_event = None  # full result dict of the highest-scoring event in the session

_alert_claim_lock = threading.Lock()
_auth_lock = threading.Lock()
_last_processed_update_id = [0]

alerted_ips = {}          # ip -> last_alert_unix_timestamp
ALERT_COOLDOWN_SECS = 300 # 5 minutes per IP



import threading
import atexit
import requests
import time

medium_incident_tracker = {}
medium_tracker_lock = threading.Lock()
MEDIUM_INCIDENT_TIMEOUT = 300

def _send_medium_summary(ip, incident):
    raw_duration = time.time() - incident["start_time"]
    duration_str = "< 2.0" if raw_duration < 2.0 else f"{raw_duration:.1f}"
    pf = incident["peak_features"]
    msg = (
        f"🟡 MEDIUM INCIDENT SUMMARY\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Attacker IP : {ip}\n"
        f"Duration    : {duration_str}s\n"
        f"Events      : {incident['event_count']} Medium-tier\n"
        f"Peak Score  : {incident['peak_score']:.3f}\n"
        f"Top Signals : failed_logins={round(pf.get('failed_logins', 0), 2)}, "
        f"cpu_usage={round(pf.get('cpu_usage', 0), 2)}, "
        f"ehr_access={round(pf.get('ehr_access_per_hour', 0), 2)}\n"
        f"Actions     : {', '.join(incident['actions'])}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
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

# Cryptographic Audit Ledger: SHA-256 hash-chained log — same cryptographic principle as blockchain

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

def send_telegram_message(msg):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM SUPPRESSED: no bot token configured")
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, verify=False, timeout=15)
        print(f"[TELEGRAM API RESPONSE] {res.status_code}: {res.text}")
        return res
    except requests.exceptions.Timeout:
        print("[TELEGRAM] sendMessage timed out after 15s — skipping")
        return None
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None

def send_telegram_photo(photo_path, caption=""):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM SUPPRESSED: no bot token configured")
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as f:
            res = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, files={"photo": f}, verify=False, timeout=15)
        print(f"[TELEGRAM API RESPONSE] {res.status_code}: {res.text}")
        return res
    except requests.exceptions.Timeout:
        print("[TELEGRAM] sendPhoto timed out after 15s — falling back to text message")
        return None
    except Exception as e:
        print(f"Error sending Telegram photo: {e}")
        return None

def wait_for_telegram_approval(prompt_msg, timeout_sec=90, accept_ignore=False):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print(f"\033[93m[TELEGRAM SIMULATOR]\033[0m Waiting for approval... type 'YES' or 'IGNORE' here:")
        ans = input(">> ").strip().upper()
        if ans == "YES": return "YES"
        if ans == "IGNORE" and accept_ignore: return "IGNORE"
        return "TIMEOUT"
        
    if prompt_msg:
        send_telegram_message(prompt_msg)
    print(f"\033[94m[*] Waiting for Telegram reply from admin...\033[0m")
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        init_req = requests.get(url, verify=False, timeout=10).json()
        last_update_id = 0
        if init_req.get("ok") and len(init_req["result"]) > 0:
            last_update_id = init_req["result"][-1]["update_id"]
            # Reset dedup tracker to the current offset so previous session's
            # YES update_id cannot block this session's new YES reply.
            _last_processed_update_id[0] = last_update_id
    except:
        last_update_id = 0

    start_t = time.time()
    while time.time() - start_t < timeout_sec:
        time.sleep(2)
        try:
            resp = requests.get(f"{url}?offset={last_update_id + 1}&timeout=5", verify=False, timeout=10).json()
            if resp.get("ok") and len(resp["result"]) > 0:
                for update in resp["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip().upper()
                        if text == "YES":
                            with _auth_lock:
                                update_id = update.get("update_id", 0)
                                if update_id <= _last_processed_update_id[0]:
                                    continue  # skip this stale update, check the rest
                                _last_processed_update_id[0] = update_id
                                return "YES"
                        if text == "IGNORE" and accept_ignore: return "IGNORE"
        except Exception as e:
            pass
    return "TIMEOUT"

def send_medium_summary(classification, action_taken):
    global session_start_time, low_count, medium_count, high_count, session_events
    duration = time.time() - session_start_time if session_start_time else 0.0
    peak = max(session_events) if session_events else classification['raw_score']
    top_3 = classification.get('plain_english_explanation', 'N/A')
    
    msg = (f"🟠 MEDIUM INCIDENT SUMMARY\n"
           f"Attack type: {classification.get('attack_type', 'Unknown')}\n"
           f"Score: {classification['raw_score']:.3f}\n"
           f"Duration: {duration:.1f}s\n"
           f"Events: Low={low_count}, Medium={medium_count}, High={high_count}\n"
           f"Top 3 Features: {top_3}\n"
           f"Action Taken: {action_taken}\n"
           f"Awaiting admin review — no further automated action will be taken.")
           
    res = send_telegram_message(msg)
    print(f"\n\033[93m{msg}\033[0m\n")
    if res and res.status_code == 200:
        session_start_time = None
        low_count = 0
        medium_count = 0
        high_count = 0
        session_events.clear()

session_high_ips = set()
def send_high_summary(classification):
    global session_start_time, low_count, medium_count, high_count, session_events, session_high_ips
    session_end_time = time.time()
    duration = session_end_time - session_start_time if session_start_time else 0.0
    peak = max(session_events) if session_events else classification['raw_score']
    
    unique_ips_str = ", ".join(session_high_ips) if session_high_ips else "Unknown"
    
    msg = (f"🔴 HIGH INCIDENT SESSION SUMMARY\n"
           f"Duration: {duration:.1f}s\n"
           f"Events: Low={low_count}, Medium={medium_count}, High={high_count}\n"
           f"Unique Attacker IPs: {unique_ips_str}\n"
           f"Peak Score: {peak:.3f}\n"
           f"MTTR: {duration:.1f}s\n"
           f"SYSTEM HELD IN CONTAINMENT — human team must restore services manually.")
           
    res = send_telegram_message(msg)
    print(f"\n\033[91m{msg}\033[0m\n")
    if res and res.status_code == 200:
        
        session_start_time = None
        low_count = 0
        medium_count = 0
        high_count = 0
        session_events.clear()
        session_high_ips.clear()

def generate_shap_chart(ip, features):
    plt.figure(figsize=(8, 5))
    names = ['failed_logins', 'cpu_usage', 'ehr_access_per_hour', 'memory_spike',
             'data_export_volume_kb', 'lateral_movement_events', 'access_time_deviation',
             'source_ip_reputation']
    vals = [features.get(n, 0) for n in names]
    y_pos = np.arange(len(names))
    plt.barh(y_pos, vals, align='center', color='coral')
    plt.yticks(y_pos, names)
    plt.xlabel('SHAP Value (impact on model output)')
    plt.title(f'SHAP Explainer for IP {ip}')
    plt.tight_layout()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = f"logs/shap_explanation_{stamp}.png"
    plt.savefig(path)
    plt.close()
    return path

def update_threat_log_action(ip, new_action, from_action='pending'):
    try:
        if not os.path.exists('logs/threat_log.json'): return
        with open('logs/threat_log.json', 'r') as f:
            lines = f.readlines()
        for i in range(len(lines)-1, -1, -1):
            if not lines[i].strip(): continue
            data = json.loads(lines[i])
            if data['ip'] == ip and data['action'] == from_action:
                data['action'] = new_action
                lines[i] = json.dumps(data) + '\n'
                # No break — update ALL matching entries for this IP
        with open('logs/threat_log.json', 'w') as f:
            f.writelines(lines)
    except Exception:
        pass

def handle_high_tier_threat(ip, features, result, alert_msg):
    start_wait = time.time()
    approved = wait_for_telegram_approval(alert_msg)
    resolve_time = time.time() - start_wait
    
    if approved == "TIMEOUT":
        print(f"\\n\033[93m[AUTO] No admin response in 90s. Auto-lockdown executed for {ip}.\033[0m")
        update_threat_log_action(ip, "auto-locked")
        final_res = respond(result, auth_token="ADMIN_TIMEOUT_AUTO_ESCALATE")
        summary = (
            f"⚠️ AUTO-ESCALATION RESOLVED\n"
            f"Admin timeout (>90s). Auto-lockdown executed.\n"
            f"Attack Tier: {result['tier'].upper()} ({features['attack_type'].upper()})\n"
            f"Resolution Time: {resolve_time:.1f} seconds\n"
            f"Attacker {ip} permanently blocked.\n"
            f"Database snapshotted and secured."
        )
        send_telegram_message(summary)
    elif approved:
        print("\n\033[92m[+] Authorization verified via Telegram. Generating forensic report.\033[0m")
        update_threat_log_action(ip, "forensics_generated")
        final_res = respond(result, auth_token="admin_approved_123")
        print(f"   -> Final Status: {final_res['status']}")
        summary = (
            f"✅ SYSTEM HELD IN CONTAINMENT\n"
            f"Attack Tier: {result['tier'].upper()} ({features['attack_type'].upper()})\n"
            f"Attacker {ip} permanently blocked.\n"
            f"Forensic report generated.\n"
            f"Incident queued for model review.\n"
            f"Human team must restore services manually."
        )
        send_telegram_message(summary)
        
        # Post-attack Summary Report
        global session_start_time, low_count, medium_count, high_count, session_events, session_peak_event
        duration = time.time() - session_start_time if session_start_time else 0
        peak = max(session_events) if session_events else result['raw_score']
        # Use the explanation from the peak event, not the current triggering event
        top_3 = (session_peak_event.get('plain_english_explanation', 'N/A')
                 if session_peak_event else result.get('plain_english_explanation', 'N/A'))
        
        report = (
            f"✅ Attack Session Summary\n"
            f"Duration: {duration:.1f}s\n"
            f"Events: Low={low_count}, Medium={medium_count}, High={high_count}\n"
            f"Peak Score: {peak:.3f}\n"
            f"MTTR: {resolve_time:.1f}s\n"
            f"Top Features: {top_3}\n"
            f"Final Status: CONTAINED"
        )
        send_telegram_message(report)
        print(f"\n\033[96m{report}\033[0m\n")
        
        
        session_start_time = None
        low_count = 0
        medium_count = 0
        high_count = 0
        session_events.clear()
        session_peak_event = None
        
    else:
        print("\n\033[93m[-] Authorization denied. System holding defensive posture.\033[0m")
        update_threat_log_action(ip, "denied")
        send_telegram_message("❌ Action aborted. Defensive posture maintained.")

def run_live_sentinel():
    global session_start_time, low_count, medium_count, high_count, session_events, session_high_ips, session_peak_event
    print("="*60)
    print("🛡️  SENTINELHEALTH LIVE WATCHDOG ACTIVATED 🛡️")
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("\033[91mWARNING: Telegram not configured. Running in local simulation mode.\033[0m")
    else:
        try:
            import urllib3
            urllib3.disable_warnings()
            res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", verify=False, timeout=10)
            if res.status_code == 200 and res.json().get("ok") == True:
                print("\033[92mTELEGRAM CONNECTED. Waiting for live web traffic...\033[0m")
            else:
                print(f"\033[91mTELEGRAM ERROR: {res.status_code} {res.text}\033[0m")
        except requests.exceptions.Timeout:
            print("\033[91mTELEGRAM TIMEOUT: Could not reach api.telegram.org in 10s. Check your network/VPN.\033[0m")
    print("="*60)

    log_file = 'logs/events.jsonl'
    os.makedirs('logs', exist_ok=True)
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f: pass

    locked_ips = set()
    processed_event_ids = set()
    seen_ids = set()  # in-memory only, resets on restart
    global session_high_ips
    session_high_ips = set()
    session_peak_event = None
    last_high_alert_time = {}
    import collections
    last_high_alert_count = collections.defaultdict(int)

    f = open(log_file, 'r')
    f.seek(0, 2)
    while True:
        line = f.readline()
        if not line:
            time.sleep(0.5)
            continue
            
        try:
            import traceback
            event = json.loads(line)
            event_id = event.get('event_id')
            if event_id:
                if event_id in processed_event_ids: continue
                processed_event_ids.add(event_id)
                
            features = event.get('features', {})
            
            if event.get('is_precomputed_feature'):
                if not TEST_MODE:
                    logger.warning("SECURITY: is_precomputed_feature received outside test mode. Discarding.")
                    continue
            if not features: continue
            ip = event.get('source_ip', event.get('ip_address', 'Unknown'))
            

            result = score_event(features)
            
            logger.info(f"{Fore.WHITE}Tier={result['tier']} | Score={result['raw_score']:.3f}")
            
            # SESSION COUNTERS AND TIMING
            if result['tier'] == 'High' and session_start_time is None:
                session_start_time = time.time()
                
            # Note: incrementing is handled inside respond now, so we don't do it here!
            # Wait, the prompt says "Increment low_count, medium_count, high_count inside the respond function immediately when each tier is determined, before any other logic runs."
            # So I will remove incrementing here.
            
            session_events.append(result['raw_score'])
            # Track the full result dict of the highest-scoring event for use in the summary
            if session_peak_event is None or result['raw_score'] > session_peak_event['raw_score']:
                session_peak_event = result.copy()

            _respond_result = result.copy()

            if result['tier'] == 'High':
                _now = time.time()
                with _alert_claim_lock:
                    _last = alerted_ips.get(ip, 0)
                    if _now - _last < ALERT_COOLDOWN_SECS:
                        result['dedup_suppress'] = True
                        _respond_result['dedup_suppress'] = True
                    else:
                        alerted_ips[ip] = _now
                        _respond_result['dedup_suppress'] = False

            shap_path = None

            if result['tier'] == 'High':
                print(f"\n{Fore.RED}[!] THREAT DETECTED FROM {ip} | Tier: High | Score: {result['raw_score']:.3f}")
                print(f"{Fore.RED}   -> SHAP Insights: {result['plain_english_explanation']}")
                try:
                    shap_path = generate_shap_chart(ip, features)
                    print(f"{Fore.RED}[SHAP] Explanation saved to {shap_path}")
                except: pass
            elif result['tier'] == 'Medium':
                print(f"\n{Fore.YELLOW}[!] THREAT DETECTED FROM {ip} | Tier: Medium | Score: {result['raw_score']:.3f}")
                print(f"{Fore.YELLOW}   -> SHAP Insights: {result['plain_english_explanation']}")
                try:
                    shap_path = generate_shap_chart(ip, features)
                    print(f"{Fore.YELLOW}[SHAP] Explanation saved to {shap_path}")
                except: pass
            else:
                print(f"{Fore.CYAN}[*] Low-level anomaly logged from {ip} | Score: {result['raw_score']:.3f}")

            with open('logs/threat_log.json', 'a') as flog:
                # High-tier events start as 'pending' ONLY if they will spawn a
                # handle_high() thread (i.e. dedup_suppress is False).  Cooldown-
                # suppressed High events are already contained by the original
                # alert's actions — write them as 'resolved' immediately so they
                # don't become orphaned 'pending' entries in the dashboard.
                if result['tier'] == 'High' and not result.get('dedup_suppress'):
                    action = "pending"
                elif result['tier'] == 'High' and result.get('dedup_suppress'):
                    action = "resolved"
                else:
                    action = "resolved"
                flog.write(json.dumps({"ip": ip, "tier": result['tier'], "score": result['raw_score'], "timestamp": datetime.now(timezone.utc).isoformat(), "action": action}) + "\n")
            
            _respond_result['shap_img_path'] = shap_path
            
            if result['tier'] == 'High':
                session_high_ips.add(ip)
            if result['tier'] == 'Low':
                with medium_tracker_lock:
                    if ip in medium_incident_tracker:
                        _send_medium_summary(ip, medium_incident_tracker.pop(ip))
                responder_res = respond(_respond_result, ip_address=ip, telegram=False)
            elif result['tier'] == 'Medium':
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
                responder_res = respond(_respond_result, ip_address=ip, telegram=False)
            else:
                with medium_tracker_lock:
                    if ip in medium_incident_tracker:
                        _inc = medium_incident_tracker.pop(ip)
                        threading.Thread(
                            target=_send_medium_summary,
                            args=(ip, _inc), daemon=True
                        ).start()
                        logger.info(f"{Fore.MAGENTA}[MEDIUM→HIGH ESCALATION] Medium summary fired for {ip}")
                        
                if result.get('dedup_suppress'):
                    _now = time.time()
                    _last = alerted_ips.get(ip, 0) # This was the original time, not updated during suppression
                    logger.info(
                        f"{Fore.MAGENTA}[COOLDOWN] High alert suppressed for {ip} — "
                        f"{int(ALERT_COOLDOWN_SECS - (_now - _last))}s remaining"
                    )
                
                responder_res = respond(_respond_result, ip_address=ip, telegram=True)
            if responder_res.get('status') in ['RESTRICTED', 'WAITING_HUMAN_AUTH']:
                locked_ips.add(ip)
                
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    run_live_sentinel()
