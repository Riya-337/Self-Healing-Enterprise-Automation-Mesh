import re

# Update live_sentinel.py
with open('live_sentinel.py', 'r') as f:
    ls_content = f.read()

run_func_match = re.search(r'def run_live_sentinel\(\):.*', ls_content, re.DOTALL)

new_run = """def run_live_sentinel():
    global session_start_time, low_count, medium_count, high_count, session_events
    print("="*60)
    print("🛡️  SENTINELHEALTH LIVE WATCHDOG ACTIVATED 🛡️")
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("\\033[91mWARNING: Telegram not configured. Running in local simulation mode.\\033[0m")
    else:
        try:
            import urllib3
            urllib3.disable_warnings()
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
                if event_id in seen_ids: continue
                seen_ids.add(event_id)
                
            features = event.get('features', {})
            if not features: continue
            ip = event.get('ip_address', 'Unknown')
            if ip in locked_ips: continue

            result = score_event(features)
            
            # SESSION COUNTERS AND TIMING
            if session_start_time is None:
                session_start_time = time.time()
                
            # Note: incrementing is handled inside respond now, so we don't do it here!
            # Wait, the prompt says "Increment low_count, medium_count, high_count inside the respond function immediately when each tier is determined, before any other logic runs."
            # So I will remove incrementing here.
            
            session_events.append(result['raw_score'])

            if result['tier'] in ['Medium', 'High']:
                print(f"\\n\\033[91m[!] THREAT DETECTED FROM {ip} | Tier: {result['tier']} | Score: {result['raw_score']:.3f}\\033[0m")
                print(f"   -> SHAP Insights: {result['plain_english_explanation']}")
                try:
                    shap_path = generate_shap_chart(ip, features)
                    print(f"\\033[96m[SHAP] Explanation saved to {shap_path}\\033[0m")
                except: pass
            else:
                print(f"\\033[93m[*] Low-level anomaly logged from {ip} | Score: {result['raw_score']:.3f}\\033[0m")

            with open('logs/threat_log.json', 'a') as flog:
                action = "pending" if result['tier'] == 'High' else "resolved"
                flog.write(json.dumps({"ip": ip, "tier": result['tier'], "score": result['raw_score'], "timestamp": datetime.now(timezone.utc).isoformat(), "action": action}) + "\\n")
            
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

            responder_res = respond(result, ip_address=ip)
            if responder_res.get('status') in ['RESTRICTED', 'WAITING_HUMAN_AUTH']:
                locked_ips.add(ip)
                
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    run_live_sentinel()
"""
ls_content = ls_content[:run_func_match.start()] + new_run

with open('live_sentinel.py', 'w') as f:
    f.write(ls_content)

# Update self_healing_responder.py
with open('self_healing_responder.py', 'r') as f:
    shr_content = f.read()

shr_match = re.search(r"elif tier == 'Medium':.*?(?=entry_str = json\.dumps)", shr_content, re.DOTALL)
new_shr_logic = """elif tier == 'Medium':
        import live_sentinel
        live_sentinel.medium_count += 1
        
        score = classification['raw_score']
        top_features = classification.get('plain_english_explanation', 'N/A')
        
        lock_account(event_id)
        block_ip(ip_address)
        
        msg = f"MEDIUM THREAT CONTAINED\\nScore: {score:.3f}\\nAttacker IP: {ip_address}\\nTop 3 features: {top_features}\\nAction taken: account locked and IP blocked."
        live_sentinel.send_telegram_message(msg)
        
        # Then print the Medium Incident Summary locally
        duration = time.time() - live_sentinel.session_start_time if live_sentinel.session_start_time else 0.0
        peak = max(live_sentinel.session_events) if live_sentinel.session_events else score
        summary_msg = (f"🟠 MEDIUM INCIDENT SUMMARY\\n"
               f"Attack type: {classification.get('attack_type', 'Unknown')}\\n"
               f"Score: {score:.3f}\\n"
               f"Duration: {duration:.1f}s\\n"
               f"Events: Low={live_sentinel.low_count}, Medium={live_sentinel.medium_count}, High={live_sentinel.high_count}\\n"
               f"Top 3 Features: {top_features}\\n"
               f"Action Taken: account locked and IP blocked\\n"
               f"no further automated action will be taken.")
        print(f"\\n\\033[93m{summary_msg}\\033[0m\\n")
        
        result = {"status": "RESTRICTED", "actions": ["account_locked", "ip_blocked"]}
        entry["actions_taken"] = result["actions"]
        entry["status"] = "RESTRICTED"
        
    elif tier == 'High':
        import live_sentinel
        live_sentinel.high_count += 1
        
        try:
            block_ip(ip_address)
            throttle_bandwidth(percent=1)
            snapshot_database()
            
            if not classification.get('dedup_suppress'):
                msg = f"CRITICAL ALERT — CONTAINMENT ACTIVE\\nIP permanently blocked, bandwidth throttled to 1%, DB snapshotted.\\nReply YES to authorize forensic report generation and retraining queue entry."
                print("ATTEMPTING HIGH TIER TELEGRAM SEND")
                
                # Add the full requests.post call with error handling
                if live_sentinel.TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN" and live_sentinel.TELEGRAM_BOT_TOKEN:
                    url = f"https://api.telegram.org/bot{live_sentinel.TELEGRAM_BOT_TOKEN}/sendMessage"
                    res = __import__('requests').post(url, json={"chat_id": live_sentinel.TELEGRAM_CHAT_ID, "text": msg}, verify=False)
                    if res.status_code != 200:
                        print(f"Telegram API Error: {res.text}")
                
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
                        
                        # High Summary
                        duration = time.time() - live_sentinel.session_start_time if live_sentinel.session_start_time else 0.0
                        peak = max(live_sentinel.session_events) if live_sentinel.session_events else classification['raw_score']
                        top_3 = classification.get('plain_english_explanation', 'N/A')
                        
                        summary_msg2 = (f"✅ Attack Session Summary\\n"
                               f"Duration: {duration:.1f}s\\n"
                               f"Events: Low={live_sentinel.low_count}, Medium={live_sentinel.medium_count}, High={live_sentinel.high_count}\\n"
                               f"Peak Score: {peak:.3f}\\n"
                               f"Top Features: {top_3}\\n"
                               f"Final Status: CONTAINED")
                               
                        if live_sentinel.TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN" and live_sentinel.TELEGRAM_BOT_TOKEN:
                            res2 = __import__('requests').post(url, json={"chat_id": live_sentinel.TELEGRAM_CHAT_ID, "text": summary_msg2}, verify=False)
                            if res2.status_code == 200:
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
            
    """

# Also fix the low_count increment
low_match = re.search(r"if tier == 'Low':", shr_content)
shr_content = shr_content[:low_match.start()] + "if tier == 'Low':\\n        import live_sentinel\\n        live_sentinel.low_count += 1\\n" + shr_content[low_match.end():]

shr_content = shr_content[:shr_match.start()] + new_shr_logic + shr_content[shr_match.end():]

# We need to run it again because low_match shifted indices, wait, I can just use replace:
shr_content = shr_content.replace("if tier == 'Low':\n        import live_sentinel\n        live_sentinel.low_count += 1\n        import live_sentinel", "if tier == 'Low':\n        import live_sentinel\n        live_sentinel.low_count += 1")

with open('self_healing_responder.py', 'w') as f:
    f.write(shr_content)

# Update attack scripts to flush
for script in ['attack_scripts/exfiltration.py', 'attack_scripts/brute_force.py']:
    with open(script, 'r') as f:
        content = f.read()
    content = content.replace("f.write(json.dumps(event) + '\\n')\\n            print", "f.write(json.dumps(event) + '\\n')\\n            f.flush()\\n            print")
    with open(script, 'w') as f:
        f.write(content)
