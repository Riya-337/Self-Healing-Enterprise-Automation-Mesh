import json
from datetime import datetime
import os
import sys
from colorama import Fore, Style, init

init(autoreset=True)

def review_queue():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    auto_approve_low = "--auto-approve-low" in args

    path = 'retraining/retraining_queue.json'
    if not os.path.exists(path):
        print(Fore.YELLOW + "No retraining queue found.")
        return
        
    queue = json.load(open(path))
    unconfirmed = [e for e in queue if not e['human_confirmed']]
    
    if not unconfirmed:
        print(Fore.GREEN + "Queue is empty. All incidents reviewed.")
        return
        
    print(Fore.CYAN + f"\n{len(unconfirmed)} incidents pending review.\n")
    
    approved_count = 0
    rejected_count = 0
    
    for i, entry in enumerate(unconfirmed):
        print(Fore.WHITE + f"[{i+1}] {entry['incident_id']}")
        print(f"     Time: {entry['timestamp']}")
        print(Fore.MAGENTA + f"     Why flagged: {entry.get('plain_english_explanation', 'No explanation provided.')}")
        
        if auto_approve_low and entry.get('tier') == 'Low':
            print(Fore.GREEN + "     [AUTO-APPROVED LOW TIER THREAT]")
            decision = 'y'
        else:
            decision = input(Fore.YELLOW + "     Approve retraining? (y/n): ").strip().lower()
            
        if decision == 'y':
            approved_count += 1
            if not dry_run:
                entry['human_confirmed'] = True
                entry['resolved_at'] = datetime.now().isoformat()
            print(Fore.GREEN + "     -> Approved\n")
        else:
            rejected_count += 1
            print(Fore.RED + "     -> Rejected\n")
            
    if not dry_run:
        json.dump(queue, open(path, 'w'), indent=2)
        print(Fore.GREEN + "Queue updated on disk.")
    else:
        print(Fore.YELLOW + "[DRY RUN] No changes written to disk.")
        
    print(Fore.CYAN + f"Summary: {approved_count} events approved, {rejected_count} events rejected, {approved_count} added to training queue.")

if __name__ == '__main__':
    review_queue()
