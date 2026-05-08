import json
import os
from flask import Flask, jsonify

app = Flask(__name__)

def get_system_state():
    status = "NORMAL"
    threats = []
    blocked_count = 0
    blockchain_status = "INTACT"

    if os.path.exists('logs/threat_log.json'):
        with open('logs/threat_log.json', 'r') as f:
            lines = [json.loads(line) for line in f if line.strip()]
            threats = list(reversed(lines))[:10]
            if threats and threats[0]['action'] == 'pending':
                status = "LOCKDOWN"
            elif threats:
                status = "THREAT"
                
    if os.path.exists('logs/blocked_ips.json'):
        with open('logs/blocked_ips.json', 'r') as f:
            blocked_count = len([line for line in f if line.strip()])
            
    if os.path.exists('logs/tamper_alerts.log'):
        with open('logs/tamper_alerts.log', 'r') as f:
            if f.read().strip():
                blockchain_status = "COMPROMISED"
                
    return {
        "status": status,
        "threats": threats,
        "blocked_count": blocked_count,
        "blockchain_status": blockchain_status
    }

@app.route('/api/status')
def api_status():
    return jsonify(get_system_state())

def get_metrics_html():
    if not os.path.exists('evaluation_metrics.json'):
        return "<p style='color: #888;'>Metrics not generated yet.</p>"
    with open('evaluation_metrics.json', 'r') as f:
        metrics = json.load(f)
        
    html = "<h3><strong>Overall Operational Performance</strong></h3>\n"
    html += "<table><thead><tr>"
    headers = ["Model", "Accuracy", "Precision", "Recall", "F1 Score", "AUC-ROC"]
    for h in headers:
        html += f"<th>{h}</th>"
    html += "</tr></thead><tbody>"
    
    for row in metrics:
        html += "<tr>"
        html += f"<td><strong>{row['model']}</strong></td>"
        html += f"<td>{row['accuracy']:.4f}</td>"
        html += f"<td>{row['precision']:.4f}</td>"
        html += f"<td>{row['recall']:.4f}</td>"
        html += f"<td>{row['f1']:.4f}</td>"
        html += f"<td>{row['auc_roc']:.4f}</td>"
        html += "</tr>"
        
    html += "</tbody></table>"
    return html

@app.route('/')
def index():
    state = get_system_state()
    metrics_html = get_metrics_html()
    
    bg_color = "#121212"
    status_color = "#4CAF50"
    if state["status"] == "THREAT": status_color = "#F44336"
    elif state["status"] == "LOCKDOWN": status_color = "#FF9800"
    
    bc_color = "#4CAF50" if state["blockchain_status"] == "INTACT" else "#F44336"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SentiHealth Dashboard</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{ font-family: -apple-system, sans-serif; background-color: {bg_color}; color: #ffffff; padding: 20px; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            .card {{ background: #1e1e1e; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
            h1, h2 {{ color: #e0e0e0; margin-top: 0; }}
            .status-badge {{ padding: 10px 20px; border-radius: 4px; font-weight: bold; background-color: {status_color}; display: inline-block; }}
            .bc-badge {{ padding: 5px 10px; border-radius: 4px; background-color: {bc_color}; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
            th {{ color: #aaa; font-weight: 500; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ SentiHealth Live Console</h1>
            
            <div class="grid">
                <div class="card">
                    <h2>System Status</h2>
                    <div class="status-badge">{state['status']}</div>
                </div>
                <div class="card">
                    <h2>Blockchain Audit Ledger</h2>
                    <span class="bc-badge">{state['blockchain_status']}</span>
                    <p style="color: #aaa; margin-top: 10px;">Total Blocked IPs: {state['blocked_count']}</p>
                </div>
            </div>
            
            <div class="card">
                <h2>Recent Threat Detections (Last 10)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>IP Address</th>
                            <th>Tier</th>
                            <th>Score</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    for t in state['threats']:
        tier_color = "#F44336" if t['tier'] == 'High' else "#FF9800"
        html += f"""
                        <tr>
                            <td>{t['timestamp']}</td>
                            <td style="font-family: monospace;">{t['ip']}</td>
                            <td style="color: {tier_color};">{t['tier']}</td>
                            <td>{t['score']:.3f}</td>
                            <td>{t['action']}</td>
                        </tr>
        """
    if not state['threats']:
        html += "<tr><td colspan='5' style='text-align:center; color:#888;'>No threats detected yet. System secure.</td></tr>"
        
    html += f"""
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h2>Machine Learning Ensemble Metrics</h2>
                {metrics_html}
            </div>
        </div>
    </body>
    </html>
    """
    return html

if __name__ == '__main__':
    print("[DASHBOARD] Running at http://localhost:5001")
    app.run(port=5001, debug=False, host='0.0.0.0')
