"""
TAMPER DEMO SCRIPT — SentiHealth Audit Chain
=============================================
Run this WHILE live_sentinel.py is active in another terminal.
It modifies the last entry's entry_hash in audit_chain.json,
breaking the SHA-256 chain and triggering:
  1. Watchdog INTEGRITY ALERT (within 8 seconds)
  2. Synchronous HALTED_CORRUPTION on next event
  3. Telegram CRITICAL alert

Usage:
  python attack_scripts/tamper_chain.py          # tamper the chain
  python attack_scripts/tamper_chain.py --restore # restore the original chain
"""

import json
import sys
import os
import shutil
from datetime import datetime

CHAIN_PATH = "data/audit_chain.json"
BACKUP_PATH = "data/audit_chain_backup.json"

def tamper():
    if not os.path.exists(CHAIN_PATH):
        print("❌ audit_chain.json not found. Is the sentinel running?")
        return

    # Backup the original chain first
    shutil.copy2(CHAIN_PATH, BACKUP_PATH)
    print(f"✅ Backup saved to {BACKUP_PATH}")

    # Load and tamper
    with open(CHAIN_PATH, "r") as f:
        chain = json.load(f)

    if len(chain) < 3:
        print("❌ Chain too short to tamper (need at least 3 entries)")
        return

    original_hash = chain[-1]["entry_hash"]
    # Flip the last character of the hash to create an invalid hash
    tampered_hash = original_hash[:-1] + ("0" if original_hash[-1] != "0" else "1")
    chain[-1]["entry_hash"] = tampered_hash

    with open(CHAIN_PATH, "w") as f:
        json.dump(chain, f)

    print(f"\n🔴 CHAIN TAMPERED at {datetime.now().strftime('%H:%M:%S')}")
    print(f"   Entry modified: #{len(chain)-1} (last entry)")
    print(f"   Original hash:  {original_hash[:40]}...")
    print(f"   Tampered hash:  {tampered_hash[:40]}...")
    print(f"\n⏳ Watchdog will detect this within 8 seconds...")
    print(f"   → Look for 'INTEGRITY ALERT' in the live_sentinel terminal")
    print(f"   → Next event will trigger HALTED_CORRUPTION + Telegram alert")
    print(f"\n💡 To restore: python attack_scripts/tamper_chain.py --restore")

def restore():
    if not os.path.exists(BACKUP_PATH):
        print("❌ No backup found. Nothing to restore.")
        return

    shutil.copy2(BACKUP_PATH, CHAIN_PATH)
    os.remove(BACKUP_PATH)
    print(f"✅ Chain restored from backup at {datetime.now().strftime('%H:%M:%S')}")
    print(f"   The system will resume normal operation on next restart.")

if __name__ == "__main__":
    if "--restore" in sys.argv:
        restore()
    else:
        tamper()
