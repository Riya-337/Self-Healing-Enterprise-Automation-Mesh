with open('self_healing_responder.py', 'r') as f:
    content = f.read()

content = content.replace(
    "import live_sentinel",
    "import sys\\nlive_sentinel = sys.modules['__main__'] if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'session_start_time') else __import__('live_sentinel')"
)

with open('self_healing_responder.py', 'w') as f:
    f.write(content)
