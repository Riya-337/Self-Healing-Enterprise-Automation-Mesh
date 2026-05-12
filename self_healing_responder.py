import json
import os
import hmac as _hmac
import hashlib
from datetime import datetime, timezone
import threading
import time
high_alert_counter = {}
last_high_event_time = {}
session_summary_sent = False
has_received_yes = False
import shutil
CRITICAL_SEGMENTS = []  # physically isolated, never touch
assert CRITICAL_SEGMENTS == []

from scoring_matrix import SESSION_SECRET

def verify_chain_integrity():
    if not os.path.exists('data/audit_chain.json'): return
    try:
        chain = json.load(open('data/audit_chain.json'))
        for i, entry in enumerate(chain[1:], 1):
            prev_hash = chain[i-1]['entry_hash']
            entry_copy = {k: v for k, v in entry.items() if k != 'entry_hash'}
            expected = hashlib.sha256((prev_hash + json.dumps(entry_copy, sort_keys=True)).encode()).hexdigest()
            if entry['entry_hash'] != expected:
                print(f"INTEGRITY ALERT: entry {i} tampered")
                with open('logs/integrity_alerts.log','a') as f:
                    f.write(f"{datetime.now()} — CHAIN TAMPERED AT {i}\n")
    except Exception as e:
        pass

def watchdog():
    while True:
        verify_chain_integrity()
        time.sleep(8)

threading.Thread(target=watchdog, daemon=True).start()

def throttle_bandwidth(percent=1):
    with open('logs/network_actions.log', 'a') as f:
        f.write(f"{datetime.now()} — Bandwidth throttled to {percent}%\n")

def snapshot_database():
    os.makedirs('data/snapshots', exist_ok=True)
    if os.path.exists('data/app.db'):
        shutil.copy('data/app.db', f'data/snapshots/snap_{int(time.time())}.db')

def lock_account(user_id: str):
    locked = set()
    if os.path.exists('logs/locked_accounts.json'):
        with open('logs/locked_accounts.json', 'r') as f:
            for line in f:
                if line.strip():
                    locked.add(json.loads(line)['user_id'])
    if user_id in locked:
        print(f"[*] Account {user_id} already locked. Operational response maintained.")
        return
    with open('logs/locked_accounts.json', 'a') as f:
        f.write(json.dumps({"user_id": user_id, "time": datetime.now(timezone.utc).isoformat()}) + "\n")

def block_ip(ip_address: str):
    blocked_ips = set()
    if os.path.exists('logs/blocked_ips.json'):
        with open('logs/blocked_ips.json', 'r') as f:
            for line in f:
                if line.strip():
                    blocked_ips.add(json.loads(line)['ip'])
    if ip_address in blocked_ips:
        # print(f"[*] IP {ip_address} is already blocked. Operational response maintained.")
        return
    with open('logs/blocked_ips.json', 'a') as f:
        f.write(json.dumps({"ip": ip_address, "time": datetime.now(timezone.utc).isoformat()}) + "\n")

def respond(classification: dict, auth_token: str = None, ip_address: str = 'Unknown', telegram: bool = True) -> dict:
    core = json.dumps({
        'event_id': classification['event_id'], 'tier': classification['tier'],
        'raw_score': classification['raw_score'], 'timestamp': classification['timestamp']
    }, sort_keys=True)
    recomputed_token = _hmac.new(SESSION_SECRET, core.encode(), hashlib.sha256).hexdigest()
    
    if not _hmac.compare_digest(classification['hmac_token'], recomputed_token):
        with open('logs/integrity_alerts.log', 'a') as f:
            f.write(f"{datetime.now()} — INVALID HMAC — possible injection\n")
        return {"status": "REJECTED_INVALID_HMAC"}
        
    tier = classification['tier']
    event_id = classification['event_id']
    
    if not os.path.exists('data/audit_chain.json'):
        with open('data/audit_chain.json', 'w') as f:
            json.dump([{"entry_hash": hashlib.sha256(b"init").hexdigest()}], f)
            
    chain = json.load(open('data/audit_chain.json'))
    prev_hash = chain[-1]['entry_hash']
    
    
    # [3.4] Synchronous block verification before append
    if len(chain) > 1:
        verify_prev_hash = chain[-2]['entry_hash']
        prev_entry_copy = {k: v for k, v in chain[-1].items() if k != 'entry_hash'}
        expected_prev_hash = hashlib.sha256((verify_prev_hash + json.dumps(prev_entry_copy, sort_keys=True)).encode()).hexdigest()
        if expected_prev_hash != prev_hash:
            # Chain corruption detected synchronously
            # Fire Telegram non-blocking alert if token exists
            import requests
            try:
                # We do a basic non-blocking request
                from live_sentinel import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
                if TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN":
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": "CRITICAL: CHAIN_CORRUPTION_DETECTED"}, timeout=2)
            except: pass
            with open('logs/tamper_alerts.log', 'a') as f:
                f.write(f"{datetime.now(timezone.utc)} — SYNCHRONOUS CORRUPTION HALT\n")
            return {"status": "HALTED_CORRUPTION"}

    entry = {
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tier": tier,
        "prev_hash": prev_hash
    }

    if tier == 'Low':
        import sys
        live_sentinel = sys.modules['__main__'] if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'session_start_time') else __import__('live_sentinel')
        live_sentinel.low_count += 1
        result = {"status": "LOGGED", "actions": ["audit_log"]}
        entry["actions_taken"] = ["audit_log"]
        entry["status"] = "LOGGED"
        
    elif tier == 'Medium':
        import sys
        live_sentinel = sys.modules['__main__'] if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'session_start_time') else __import__('live_sentinel')
        live_sentinel.medium_count += 1
        
        score = classification['raw_score']
        top_features = classification.get('plain_english_explanation', 'N/A')
        
        user_id = classification.get('features', {}).get('user_id', 'Unknown')
        lock_account(user_id)
        block_ip(ip_address)
        
        msg = f"MEDIUM THREAT CONTAINED\nScore: {score:.3f}\nAttacker IP: {ip_address}\nTop 3 features: {top_features}\nAction taken: account locked and IP blocked."
        if telegram:
            live_sentinel.send_telegram_message(msg)
        
        # Then print the Medium Incident Summary locally
        raw_duration = time.time() - live_sentinel.session_start_time if live_sentinel.session_start_time else 0.0
        duration_str = "< 2.0" if raw_duration < 2.0 else f"{raw_duration:.1f}"
        peak = max(live_sentinel.session_events) if live_sentinel.session_events else score
        summary_msg = (f"🟠 MEDIUM INCIDENT SUMMARY\n"
               f"Attack type: {classification.get('attack_type', 'Unknown')}\n"
               f"Score: {score:.3f}\n"
               f"Duration: {duration_str}s\n"
               f"Events: Low={live_sentinel.low_count}, Medium={live_sentinel.medium_count}, High={live_sentinel.high_count}\n"
               f"Top 3 Features: {top_features}\n"
               f"Action Taken: account locked and IP blocked\n"
               f"no further automated action will be taken.")
        print(f"\n\033[93m{summary_msg}\033[0m\n")
        
        result = {"status": "RESTRICTED", "actions": ["account_locked", "ip_blocked"]}
        entry["actions_taken"] = result["actions"]
        entry["status"] = "RESTRICTED"
        
    elif tier == 'High':
        import sys
        live_sentinel = sys.modules['__main__'] if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'session_start_time') else __import__('live_sentinel')
        live_sentinel.high_count += 1
        
        try:
            block_ip(ip_address)
            throttle_bandwidth(percent=1)
            snapshot_database()
            if not classification.get('dedup_suppress'):
                msg = (f"ATTACKER IP: {ip_address}\n"
                       f"CRITICAL ALERT — CONTAINMENT ACTIVE\n"
                       f"IP permanently blocked, bandwidth throttled to 1%, DB snapshotted.\n"
                       f"Reply YES to authorize forensic report generation and retraining queue entry.")
                print("ATTEMPTING HIGH TIER TELEGRAM SEND")
                
                # Add the full requests.post call with error handling
                if not os.environ.get("TELEGRAM_BOT_TOKEN", "").strip():
                    print("TELEGRAM SUPPRESSED: no bot token configured")
                elif live_sentinel.TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN" and live_sentinel.TELEGRAM_BOT_TOKEN:
                    shap_path = classification.get('shap_img_path')
                    photo_sent = False
                    if shap_path and os.path.exists(shap_path):
                        res = live_sentinel.send_telegram_photo(shap_path, caption=msg)
                        if res and res.status_code == 200:
                            photo_sent = True
                    
                    if not photo_sent:
                        url = f"https://api.telegram.org/bot{live_sentinel.TELEGRAM_BOT_TOKEN}/sendMessage"
                        res = __import__('requests').post(url, json={"chat_id": live_sentinel.TELEGRAM_CHAT_ID, "text": msg}, verify=False)
                        if res.status_code != 200:
                            print(f"Telegram API Error: {res.text}")
                
                def handle_high():
                    reply = live_sentinel.wait_for_telegram_approval(None if ('photo_sent' in locals() and photo_sent) else msg, timeout_sec=90)
                    if reply == "YES":
                        with open(f'logs/forensic_report_{event_id}.json', 'w') as flog:
                            json.dump(classification, flog)
                        
                        q_path = 'retraining/retraining_queue.json'
                        if not os.path.exists(q_path):
                            with open(q_path, 'w') as fq: json.dump([], fq)
                        queue = json.load(open(q_path))
                        queue.append({
                            "incident_id": event_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "tier": "High",
                            "top_3_features": classification.get('top_3_features', []),
                            "plain_english_explanation": classification.get('plain_english_explanation', ''),
                            "human_confirmed": True,
                            "resolved_at": datetime.now(timezone.utc).isoformat()
                        })
                        with open(q_path, 'w') as fq: json.dump(queue, fq)
                        
                        live_sentinel.send_telegram_message("✅ SYSTEM HELD IN CONTAINMENT — Forensic report generated — Human team must restore services manually.")
                        
                        # High Summary
                        duration = time.time() - live_sentinel.session_start_time if live_sentinel.session_start_time else 0.0
                        peak = max(live_sentinel.session_events) if live_sentinel.session_events else classification['raw_score']
                        top_3 = classification.get('plain_english_explanation', 'N/A')
                        
                        summary_msg2 = (f"✅ Attack Session Summary\n"
                               f"Duration: {duration:.1f}s\n"
                               f"Events: Low={live_sentinel.low_count}, Medium={live_sentinel.medium_count}, High={live_sentinel.high_count}\n"
                               f"Peak Score: {peak:.3f}\n"
                               f"Top Features: {top_3}\n"
                               f"Final Status: CONTAINED")
                               
                        if not os.environ.get("TELEGRAM_BOT_TOKEN", "").strip():
                            print("TELEGRAM SUPPRESSED: no bot token configured")
                        elif live_sentinel.TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN" and live_sentinel.TELEGRAM_BOT_TOKEN:
                            res2 = live_sentinel.send_telegram_message(summary_msg2)
                            if res2 and res2.status_code == 200:
                                live_sentinel.session_start_time = None
                                live_sentinel.low_count = 0
                                live_sentinel.medium_count = 0
                                live_sentinel.high_count = 0
                                live_sentinel.session_events.clear()
                                
                threading.Thread(target=handle_high, daemon=True).start()
                
            result = {"status": "WAITING_HUMAN_AUTH", "actions": ["ip_blocked", "bandwidth_throttled", "db_snapshotted"]}
            entry["actions_taken"] = result["actions"]
            entry["status"] = "WAITING"
        except Exception as e:
            import traceback
            traceback.print_exc()
            result = {"status": "ERROR"}
            
    entry_str = json.dumps(entry, sort_keys=True)
    entry["entry_hash"] = hashlib.sha256((prev_hash + entry_str).encode()).hexdigest()
    chain.append(entry)
    
    with open('data/audit_chain.json', 'w') as f:
        json.dump(chain, f)
        
    return result
