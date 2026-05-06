import os
import re

# ==========================================
# FIX 1: Multi-IP in Attack Scripts
# ==========================================
for script in ['attack_scripts/exfiltration.py']:
    if os.path.exists(script):
        with open(script, 'r') as f:
            content = f.read()
        
        # Replace the hardcoded ip_address
        content = re.sub(r'"ip_address":\s*"::ffff:192\.168\.1\.100"', '"source_ip": "10.0.0.47" if idx == 0 else ("10.0.0.83" if idx == 1 else ("10.0.0.47" if event_idx % 2 == 0 else "10.0.0.83")), "ip_address": "::ffff:192.168.1.100"', content)
        
        # We need event_idx for the alternating logic.
        content = content.replace("for _ in range(5):", "for event_idx in range(5):")
        
        with open(script, 'w') as f:
            f.write(content)

if os.path.exists('attack_scripts/brute_force.py'):
    with open('attack_scripts/brute_force.py', 'r') as f:
        content = f.read()
    
    # Pass idx down to burst
    content = content.replace("def burst(count):", "def burst(count, idx):")
    content = content.replace("burst(5)", "burst(5, idx)")
    
    # Update payload
    content = re.sub(
        r'json=\{"username": "admin", "password": f"pass\{i\}"\}',
        r'json={"username": "admin", "password": f"pass{i}", "source_ip": "10.0.0.47" if idx == 0 else ("10.0.0.83" if idx == 1 else ("10.0.0.47" if i % 2 == 0 else "10.0.0.83"))}',
        content
    )
    with open('attack_scripts/brute_force.py', 'w') as f:
        f.write(content)

# ==========================================
# FIX 2 & FIX 1: live_sentinel.py updates
# ==========================================
with open('live_sentinel.py', 'r') as f:
    ls_content = f.read()

# Fix 1: extract source_ip
ls_content = ls_content.replace(
    "ip = event.get('ip_address', 'Unknown')",
    "ip = event.get('source_ip', event.get('ip_address', 'Unknown'))"
)
ls_content = ls_content.replace(
    "ip = event.get('features', {}).get('ip_address', 'Unknown')",
    "ip = event.get('source_ip', event.get('features', {}).get('ip_address', 'Unknown'))"
)

# Fix 2: processed_event_ids
if "processed_event_ids = set()" not in ls_content:
    ls_content = ls_content.replace("seen_ids = set()", "processed_event_ids = set()\\n    seen_ids = set()")
    ls_content = ls_content.replace(
        "if event_id in seen_ids: continue\\n                seen_ids.add(event_id)",
        "if event_id in processed_event_ids: continue\\n                processed_event_ids.add(event_id)"
    )

# Fix 3: Remove dedup logic from live_sentinel since we are moving it to self_healing_responder
dedup_block = re.search(r"if result\['tier'\] == 'High':\s*session_high_ips\.add\(ip\)\s*current_t = time\.time\(\)\s*if ip in last_high_alert_time.*?(?=responder_res = respond)", ls_content, re.DOTALL)
if dedup_block:
    new_high = "if result['tier'] == 'High':\\n                session_high_ips.add(ip)\\n            "
    ls_content = ls_content[:dedup_block.start()] + new_high + ls_content[dedup_block.end():]


with open('live_sentinel.py', 'w') as f:
    f.write(ls_content)


# ==========================================
# FIX 3 & 4: self_healing_responder.py updates
# ==========================================
with open('self_healing_responder.py', 'r') as f:
    shr_content = f.read()

# Add global state for Fix 3 and 4 at the top
if "high_alert_counter = {}" not in shr_content:
    shr_content = shr_content.replace("import time", "import time\\nhigh_alert_counter = {}\\nlast_high_event_time = {}\\nsession_summary_sent = False\\nhas_received_yes = False\\n")

high_tier_block = re.search(r"elif tier == 'High':.*?(?=\\n    entry_str = json\.dumps)", shr_content, re.DOTALL)
if high_tier_block:
    new_high_tier = """elif tier == 'High':
        import sys
        live_sentinel = sys.modules['__main__'] if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'session_start_time') else __import__('live_sentinel')
        live_sentinel.high_count += 1
        
        global high_alert_counter, last_high_event_time, session_summary_sent, has_received_yes
        
        try:
            block_ip(ip_address)
            throttle_bandwidth(percent=1)
            snapshot_database()
            
            # FIX 3: high_alert_counter
            if ip_address not in high_alert_counter:
                high_alert_counter[ip_address] = 0
            high_alert_counter[ip_address] += 1
            
            current_time = time.time()
            last_high_event_time[ip_address] = current_time
            
            # Dedup logic:
            if high_alert_counter[ip_address] == 1 or (current_time - last_high_event_time.get(ip_address, 0)) >= 45:
                # Full alert
                msg = f"CRITICAL ALERT — CONTAINMENT ACTIVE\\nIP permanently blocked, bandwidth throttled to 1%, DB snapshotted.\\nReply YES to authorize forensic report generation and retraining queue entry."
                print("ATTEMPTING HIGH TIER TELEGRAM SEND")
                
                if live_sentinel.TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN" and live_sentinel.TELEGRAM_BOT_TOKEN:
                    url = f"https://api.telegram.org/bot{live_sentinel.TELEGRAM_BOT_TOKEN}/sendMessage"
                    res = __import__('requests').post(url, json={"chat_id": live_sentinel.TELEGRAM_CHAT_ID, "text": msg}, verify=False)
                    if res.status_code != 200:
                        print(f"Telegram API Error: {res.text}")
                
                def handle_high():
                    global has_received_yes, session_summary_sent, high_alert_counter, last_high_event_time
                    reply = live_sentinel.wait_for_telegram_approval(msg, timeout_sec=90)
                    if reply == "YES":
                        has_received_yes = True
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
                        
                        # Wait for 30 seconds of no new high events from any IP? Or just this IP?
                        # "after no new High tier event has arrived for 30 seconds following the last High event."
                        # This means we should check the MAXIMUM of all last_high_event_time
                        while True:
                            time.sleep(5)
                            if time.time() - max(last_high_event_time.values()) >= 30:
                                break
                                
                        if not session_summary_sent:
                            session_summary_sent = True
                            live_sentinel.send_high_summary(classification)
                            has_received_yes = False
                            session_summary_sent = False
                            high_alert_counter.clear()
                            last_high_event_time.clear()
                            
                threading.Thread(target=handle_high, daemon=True).start()
            else:
                # Repeated alert
                short_msg = f"REPEATED HIGH ALERT number {high_alert_counter[ip_address]} from same attacker {ip_address}, score {classification['raw_score']:.3f}"
                if live_sentinel.TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN" and live_sentinel.TELEGRAM_BOT_TOKEN:
                    url = f"https://api.telegram.org/bot{live_sentinel.TELEGRAM_BOT_TOKEN}/sendMessage"
                    __import__('requests').post(url, json={"chat_id": live_sentinel.TELEGRAM_CHAT_ID, "text": short_msg}, verify=False)
            
            result = {"status": "WAITING_HUMAN_AUTH", "actions": ["ip_blocked", "bandwidth_throttled", "db_snapshotted"]}
            entry["actions_taken"] = result["actions"]
            entry["status"] = "WAITING"
        except Exception as e:
            import traceback
            traceback.print_exc()
            result = {"status": "ERROR"}
        """
    shr_content = shr_content[:high_tier_block.start()] + new_high_tier + shr_content[high_tier_block.end():]

with open('self_healing_responder.py', 'w') as f:
    f.write(shr_content)
