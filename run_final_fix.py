import re

# Update live_sentinel.py
with open('live_sentinel.py', 'r') as f:
    ls_content = f.read()

# Fix 1: Remove `if ip in locked_ips: continue`
ls_content = ls_content.replace("if ip in locked_ips: continue", "")

# Fix 4: Change High dedup timer to 45 seconds
ls_content = ls_content.replace(
    "if ip in last_high_alert_time and (current_t - last_high_alert_time[ip]) < 30:",
    "if ip in last_high_alert_time and (current_t - last_high_alert_time[ip]) < 45:"
)

# We need to track unique high attacker IPs.
# Let's add session_high_ips tracking.
run_sent_match = re.search(r'def run_live_sentinel\(\):.*', ls_content, re.DOTALL)
if run_sent_match:
    new_run = run_sent_match.group(0)
    
    # Add session_high_ips inside run_live_sentinel if it doesn't exist
    if "session_high_ips =" not in new_run:
        new_run = new_run.replace("global session_start_time, low_count, medium_count, high_count, session_events", "global session_start_time, low_count, medium_count, high_count, session_events, session_high_ips")
        new_run = new_run.replace("seen_ids = set()", "seen_ids = set()\\n    global session_high_ips\\n    session_high_ips = set()")
        
        # When tier == 'High', add to session_high_ips
        new_run = new_run.replace("if result['tier'] == 'High':\\n                current_t = time.time()", "if result['tier'] == 'High':\\n                session_high_ips.add(ip)\\n                current_t = time.time()")
        
    ls_content = ls_content[:run_sent_match.start()] + new_run

# Fix 5: Change High session summary message
# In send_high_summary:
old_high_summary = """def send_high_summary(classification):
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

new_high_summary = """session_high_ips = set()
def send_high_summary(classification):
    global session_start_time, low_count, medium_count, high_count, session_events, session_high_ips
    session_end_time = time.time()
    duration = session_end_time - session_start_time if session_start_time else 0.0
    peak = max(session_events) if session_events else classification['raw_score']
    
    unique_ips_str = ", ".join(session_high_ips) if session_high_ips else "Unknown"
    
    msg = (f"🔴 HIGH INCIDENT SESSION SUMMARY\\n"
           f"Duration: {duration:.1f}s\\n"
           f"Events: Low={low_count}, Medium={medium_count}, High={high_count}\\n"
           f"Unique Attacker IPs: {unique_ips_str}\\n"
           f"Peak Score: {peak:.3f}\\n"
           f"MTTR: {duration:.1f}s\\n"
           f"SYSTEM HELD IN CONTAINMENT — human team must restore services manually.")
           
    res = send_telegram_message(msg)
    print(f"\\n\\033[91m{msg}\\033[0m\\n")
    if res and res.status_code == 200:
        session_start_time = None
        low_count = 0
        medium_count = 0
        high_count = 0
        session_events.clear()
        session_high_ips.clear()"""

ls_content = ls_content.replace(old_high_summary, new_high_summary)

with open('live_sentinel.py', 'w') as f:
    f.write(ls_content)


# Update self_healing_responder.py
with open('self_healing_responder.py', 'r') as f:
    shr_content = f.read()

# Fix 2 & 3: Make block_ip and lock_account idempotent and not filtering
block_ip_old = """def block_ip(ip_address: str):
    with open('logs/blocked_ips.json', 'a') as f:
        f.write(json.dumps({"ip": ip_address, "time": datetime.now(timezone.utc).isoformat()}) + "\\n")"""

block_ip_new = """def block_ip(ip_address: str):
    blocked_ips = set()
    if os.path.exists('logs/blocked_ips.json'):
        with open('logs/blocked_ips.json', 'r') as f:
            for line in f:
                if line.strip():
                    blocked_ips.add(json.loads(line)['ip'])
    if ip_address in blocked_ips:
        print(f"[*] IP {ip_address} is already blocked. Operational response maintained.")
        return
    with open('logs/blocked_ips.json', 'a') as f:
        f.write(json.dumps({"ip": ip_address, "time": datetime.now(timezone.utc).isoformat()}) + "\\n")"""

lock_account_old = """def lock_account(user_id: str):
    with open('logs/locked_accounts.json', 'a') as f:
        f.write(json.dumps({"user_id": user_id, "time": datetime.now(timezone.utc).isoformat()}) + "\\n")"""

lock_account_new = """def lock_account(user_id: str):
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
        f.write(json.dumps({"user_id": user_id, "time": datetime.now(timezone.utc).isoformat()}) + "\\n")"""

shr_content = shr_content.replace(block_ip_old, block_ip_new)
shr_content = shr_content.replace(lock_account_old, lock_account_new)

# In Medium tier, fix the user_id for lock_account (it was event_id accidentally in previous pass!)
# wait, previously I had lock_account(event_id) instead of user_id. Let's fix that too.
shr_content = shr_content.replace("lock_account(event_id)", "user_id = classification.get('features', {}).get('user_id', 'Unknown')\\n        lock_account(user_id)")

# In High tier, update the send_high_summary parameter if needed (already updated in live_sentinel)

with open('self_healing_responder.py', 'w') as f:
    f.write(shr_content)
