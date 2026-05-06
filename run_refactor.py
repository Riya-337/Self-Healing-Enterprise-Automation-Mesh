import re

with open('live_sentinel.py', 'r') as f:
    ls_content = f.read()

ls_content = ls_content.replace(
"""def send_telegram_message(msg):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM SUPPRESSED: no bot token configured")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, verify=False)
        print(f"[TELEGRAM API RESPONSE] {res.status_code}: {res.text}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")""",
"""def send_telegram_message(msg):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM SUPPRESSED: no bot token configured")
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, verify=False)
        print(f"[TELEGRAM API RESPONSE] {res.status_code}: {res.text}")
        return res
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None"""
)

ls_content = ls_content.replace(
"""def wait_for_telegram_approval(prompt_msg):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print(f"\\033[93m[TELEGRAM SIMULATOR]\\033[0m Waiting for approval... type 'YES' here:")
        return input(">> ").strip().upper() == "YES"
        
    send_telegram_message(prompt_msg)
    print(f"\\033[94m[*] Waiting for Telegram reply ('YES') from admin...\\033[0m")
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        init_req = requests.get(url, verify=False).json()
        last_update_id = 0
        if init_req.get("ok") and len(init_req["result"]) > 0:
            last_update_id = init_req["result"][-1]["update_id"]
    except:
        last_update_id = 0

    start_t = time.time()
    while time.time() - start_t < 90:
        time.sleep(2)
        try:
            resp = requests.get(f"{url}?offset={last_update_id + 1}&timeout=5", verify=False).json()
            if resp.get("ok") and len(resp["result"]) > 0:
                for update in resp["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip().upper()
                        if text == "YES":
                            return True
                        elif text == "NO":
                            return False
        except Exception as e:
            pass
    return "TIMEOUT"

def tail_logs(filepath):
    \"\"\"Generator to continuously yield new lines from a file.\"\"\"
    with open(filepath, 'r') as f:
        f.seek(0, 2)  # Go to end of file
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            yield line""",
"""def wait_for_telegram_approval(prompt_msg, timeout_sec=90, accept_ignore=False):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print(f"\\033[93m[TELEGRAM SIMULATOR]\\033[0m Waiting for approval... type 'YES' or 'IGNORE' here:")
        ans = input(">> ").strip().upper()
        if ans == "YES": return "YES"
        if ans == "IGNORE" and accept_ignore: return "IGNORE"
        return "TIMEOUT"
        
    send_telegram_message(prompt_msg)
    print(f"\\033[94m[*] Waiting for Telegram reply from admin...\\033[0m")
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        init_req = requests.get(url, verify=False).json()
        last_update_id = 0
        if init_req.get("ok") and len(init_req["result"]) > 0:
            last_update_id = init_req["result"][-1]["update_id"]
    except:
        last_update_id = 0

    start_t = time.time()
    while time.time() - start_t < timeout_sec:
        time.sleep(2)
        try:
            resp = requests.get(f"{url}?offset={last_update_id + 1}&timeout=5", verify=False).json()
            if resp.get("ok") and len(resp["result"]) > 0:
                for update in resp["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip().upper()
                        if text == "YES": return "YES"
                        if text == "IGNORE" and accept_ignore: return "IGNORE"
        except Exception as e:
            pass
    return "TIMEOUT"

def send_medium_summary(classification, action_taken):
    global session_start_time, low_count, medium_count, high_count, session_events
    duration = time.time() - session_start_time if session_start_time else 0.0
    peak = max(session_events) if session_events else classification['raw_score']
    top_3 = classification.get('plain_english_explanation', 'N/A')
    
    msg = (f"🟠 MEDIUM INCIDENT SUMMARY\\n"
           f"Attack type: {classification.get('attack_type', 'Unknown')}\\n"
           f"Score: {classification['raw_score']:.3f}\\n"
           f"Duration: {duration:.1f}s\\n"
           f"Events: Low={low_count}, Medium={medium_count}, High={high_count}\\n"
           f"Top 3 Features: {top_3}\\n"
           f"Action Taken: {action_taken}\\n"
           f"Awaiting admin review — no further automated action will be taken.")
           
    res = send_telegram_message(msg)
    print(f"\\n\\033[93m{msg}\\033[0m\\n")
    if res and res.status_code == 200:
        session_start_time = None
        low_count = 0
        medium_count = 0
        high_count = 0
        session_events.clear()

def send_high_summary(classification):
    global session_start_time, low_count, medium_count, high_count, session_events
    session_end_time = time.time()
    duration = session_end_time - session_start_time if session_start_time else 0.0
    peak = max(session_events) if session_events else classification['raw_score']
    top_3 = classification.get('plain_english_explanation', 'N/A')
    
    msg = (f"✅ Attack Session Summary\\n"
           f"Duration: {duration:.1f}s\\n"
           f"Events: Low={low_count}, Medium={medium_count}, High={high_count}\\n"
           f"Peak Score: {peak:.3f}\\n"
           f"Top Features: {top_3}\\n"
           f"Final Status: CONTAINED")
           
    res = send_telegram_message(msg)
    print(f"\\n\\033[96m{msg}\\033[0m\\n")
    if res and res.status_code == 200:
        session_start_time = None
        low_count = 0
        medium_count = 0
        high_count = 0
        session_events.clear()"""
)

# Replace the run_live_sentinel logic
run_sent_regex = r'def run_live_sentinel\(\):.*'
run_func_match = re.search(run_sent_regex, ls_content, re.DOTALL)

new_run = """def run_live_sentinel():
    global session_start_time, low_count, medium_count, high_count, session_events
    print("="*60)
    print("🛡️  SENTINELHEALTH LIVE WATCHDOG ACTIVATED 🛡️")
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("\\033[91mWARNING: Telegram not configured. Running in local simulation mode.\\033[0m")
    else:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", verify=False)
            if res.status_code == 200 and res.json().get("ok") == True:
                print("\\033[92mTELEGRAM CONNECTED. Waiting for live web traffic...\\033[0m")
            else:
                print(f"\\033[91mTELEGRAM ERROR: {res.status_code} {res.text}\\033[0m")
        except Exception as e:
            print(f"\\033[91mTELEGRAM CONNECTION FAILED: {e}\\033[0m")
    print("="*60)

    log_file = 'logs/events.jsonl'
    os.makedirs('logs', exist_ok=True)
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f: pass

    locked_ips = set()
    seen_ids = set()
    last_high_alert_time = {}
    last_high_alert_count = defaultdict(int)

    with open(log_file, 'r') as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
                
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            event_id = event.get('event_id')
            if event_id:
                if event_id in seen_ids: continue
                seen_ids.add(event_id)
                
            features = event.get('features', {})
            if not features: continue
            ip = event.get('ip_address', 'Unknown')
            if ip in locked_ips: continue

            result = score_event(features)
            
            # FIX 7: Set session_start_time the moment the first event of any tier is processed
            if session_start_time is None:
                session_start_time = time.time()
                
            if result['tier'] == 'Low': low_count += 1
            elif result['tier'] == 'Medium': medium_count += 1
            elif result['tier'] == 'High': high_count += 1
            session_events.append(result['raw_score'])

            if result['tier'] in ['Medium', 'High']:
                print(f"\\n\\033[91m[!] THREAT DETECTED FROM {ip} | Tier: {result['tier']} | Score: {result['raw_score']:.3f}\\033[0m")
                print(f"   -> SHAP Insights: {result['plain_english_explanation']}")
                try:
                    shap_path = generate_shap_chart(ip, features)
                    print(f"\\033[96m[SHAP] Explanation saved to {shap_path}\\033[0m")
                except:
                    pass
            else:
                print(f"\\033[93m[*] Low-level anomaly logged from {ip} | Score: {result['raw_score']:.3f}\\033[0m")

            with open('logs/threat_log.json', 'a') as flog:
                action = "pending" if result['tier'] == 'High' else "resolved"
                flog.write(json.dumps({"ip": ip, "tier": result['tier'], "score": result['raw_score'], "timestamp": datetime.now(timezone.utc).isoformat(), "action": action}) + "\\n")
            
            # FIX 2: Dedup high alerts
            if result['tier'] == 'High':
                current_t = time.time()
                if ip in last_high_alert_time and (current_t - last_high_alert_time[ip]) < 30:
                    last_high_alert_count[ip] += 1
                    msg = f"REPEATED HIGH ALERT number {last_high_alert_count[ip]} from same attacker IP {ip}, score {result['raw_score']:.3f}"
                    send_telegram_message(msg)
                    result['dedup_suppress'] = True
                else:
                    last_high_alert_time[ip] = current_t
                    last_high_alert_count[ip] = 1
                    result['dedup_suppress'] = False

            # Call responder
            responder_res = respond(result, ip_address=ip)
            if responder_res.get('status') in ['RESTRICTED', 'WAITING_HUMAN_AUTH']:
                locked_ips.add(ip)

if __name__ == '__main__':
    run_live_sentinel()
"""
ls_content = ls_content[:run_func_match.start()] + new_run

with open('live_sentinel.py', 'w') as f:
    f.write(ls_content)


# Update self_healing_responder.py
with open('self_healing_responder.py', 'r') as f:
    shr_content = f.read()

shr_content = shr_content.replace(
    "def respond(classification: dict, auth_token: str = None) -> dict:",
    "def respond(classification: dict, auth_token: str = None, ip_address: str = 'Unknown') -> dict:"
)

shr_match = re.search(r"elif tier == 'Medium':.*?(?=entry_str = json\.dumps)", shr_content, re.DOTALL)
new_shr_logic = """elif tier == 'Medium':
        import live_sentinel
        score = classification['raw_score']
        top_features = classification.get('plain_english_explanation', 'N/A')
        
        msg = f"MEDIUM THREAT DETECTED\\nScore: {score:.3f}\\nTop features: {top_features}\\nAttacker IP: {ip_address}\\nReply YES to approve account lock and IP block or IGNORE to dismiss."
        
        def handle_medium():
            reply = live_sentinel.wait_for_telegram_approval(msg, timeout_sec=60, accept_ignore=True)
            if reply == "YES":
                lock_account(event_id)
                block_ip(ip_address)
                live_sentinel.send_telegram_message("✅ Account locked, IP blocked.")
                live_sentinel.send_medium_summary(classification, "Account locked, IP blocked")
            elif reply == "IGNORE":
                print("Medium threat dismissed via IGNORE.")
                with open('logs/threat_log.json', 'a') as flog:
                    flog.write(json.dumps({"event_id": event_id, "action": "dismissed", "time": datetime.now(timezone.utc).isoformat()}) + "\\n")
            else:
                lock_account(event_id)
                block_ip(ip_address)
                live_sentinel.send_telegram_message("⏳ Auto-approved after 60s timeout — account locked, IP blocked.")
                live_sentinel.send_medium_summary(classification, "Account locked, IP blocked (Auto-approved)")
        
        threading.Thread(target=handle_medium, daemon=True).start()
        
        result = {"status": "RESTRICTED", "actions": ["pending_consent"]}
        entry["actions_taken"] = result["actions"]
        entry["status"] = "RESTRICTED"
        
    elif tier == 'High':
        block_ip(ip_address)
        throttle_bandwidth(percent=1)
        snapshot_database()
        
        import live_sentinel
        
        if not classification.get('dedup_suppress'):
            msg = f"CRITICAL ALERT — CONTAINMENT ACTIVE\\nIP permanently blocked, bandwidth throttled to 1%, DB snapshotted.\\nReply YES to authorize forensic report generation and retraining queue entry."
            
            def handle_high():
                reply = live_sentinel.wait_for_telegram_approval(msg, timeout_sec=90)
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
                    live_sentinel.send_high_summary(classification)
                    
            threading.Thread(target=handle_high, daemon=True).start()
            
        result = {"status": "WAITING_HUMAN_AUTH", "actions": ["ip_blocked", "bandwidth_throttled", "db_snapshotted"]}
        entry["actions_taken"] = result["actions"]
        entry["status"] = "WAITING"
        
    """
shr_content = shr_content[:shr_match.start()] + new_shr_logic + shr_content[shr_match.end():]

with open('self_healing_responder.py', 'w') as f:
    f.write(shr_content)
