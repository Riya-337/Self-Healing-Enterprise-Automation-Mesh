import os

with open('live_sentinel.py', 'r') as f:
    content = f.read()

# FIX 1: load_dotenv and config validator at top
fix_1 = """from dotenv import load_dotenv
load_dotenv()  # loads .env into os.environ automatically

def _check_config():
    required = {
        "TELEGRAM_BOT_TOKEN": "High-tier alerts",
        "TELEGRAM_CHAT_ID":   "All Telegram notifications",
    }
    optional = {
        "SENTIHEALTH_TEST_MODE": "Test mode bypass (default: off)",
    }
    print("\\n[CONFIG CHECK]")
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

"""

if "load_dotenv()" not in content:
    content = content.replace("import logging\n", "import logging\n" + fix_1)


# FIX 2: High-Tier Cooldown Race and FIX 3: YES Reply Race locks
fix_locks = """_alert_claim_lock = threading.Lock()
_auth_lock = threading.Lock()
_last_processed_update_id = [0]
"""

if "_alert_claim_lock" not in content:
    content = content.replace("alerted_ips = {}", fix_locks + "\nalerted_ips = {}")

# FIX 2 replacement in High-Tier block
cooldown_old = """            else:
                _now = time.time()
                _last = alerted_ips.get(ip, 0)
                if _now - _last < ALERT_COOLDOWN_SECS:
                    logger.info(f"[COOLDOWN] High alert suppressed for {ip} — {int(ALERT_COOLDOWN_SECS-(_now-_last))}s remaining")
                    result['dedup_suppress'] = True
                else:
                    alerted_ips[ip] = _now
                responder_res = respond(result, ip_address=ip, telegram=True)"""

cooldown_new = """            else:
                _now = time.time()
                _send_telegram = False
                with _alert_claim_lock:
                    _last = alerted_ips.get(ip, 0)
                    if _now - _last < ALERT_COOLDOWN_SECS:
                        logger.info(
                            f"[COOLDOWN] High alert suppressed for {ip} — "
                            f"{int(ALERT_COOLDOWN_SECS - (_now - _last))}s remaining"
                        )
                        result['dedup_suppress'] = True
                    else:
                        alerted_ips[ip] = _now
                        _send_telegram = True
                
                responder_res = respond(result, ip_address=ip, telegram=True)"""

if "with _alert_claim_lock:" not in content:
    content = content.replace(cooldown_old, cooldown_new)

# FIX 3: YES Reply Race Condition
# We need to wrap the YES handling in wait_for_telegram_approval in live_sentinel.py
yes_old = """                        if text == "YES": return "YES\""""
yes_new = """                        if text == "YES":
                            with _auth_lock:
                                update_id = update.get("update_id", 0)
                                if update_id <= _last_processed_update_id[0]:
                                    break
                                _last_processed_update_id[0] = update_id
                                return "YES\""""

if "_last_processed_update_id[0] = update_id" not in content:
    content = content.replace(yes_old, yes_new)

with open('live_sentinel.py', 'w') as f:
    f.write(content)
