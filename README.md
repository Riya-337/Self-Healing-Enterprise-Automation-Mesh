# SentiHealth

Autonomous AI cybersecurity and self-healing framework for healthcare infrastructure.

## Architecture

```text
       [1. Target]                      [2. Watchdog]                        [3. AI Ensemble]
 +-------------------+           +-----------------------+              +-----------------------+
 |   Node.js EHR     |   logs    | live_sentinel.py      |   features   | scikit-learn Models   |
 |   Server (:3000)  | ========> | (Feature Aggregation) | ===========> | (RF, GB, SVM, LR, XGB)|
 +-------------------+           +-----------------------+              +-----------------------+
                                            |                                       |
                                            |                                       v
                                            |                             [4. Self-Healing]
                                            |                           +-----------------------+
                                            +<==========================| self_healing_responder|
                                               action/status            +-----------------------+
                                                                          |                   |
                                                                   [Lockdown]           [Audit Ledger]
                                                                          |                   |
                                                                          v                   v
                                                              +----------------+   +-------------------+
                                                              | Telegram Alert |   | audit_chain.json  |
                                                              +----------------+   +-------------------+
```

## Quickstart (5 Steps)

1. **Install dependencies**: `source setup.sh`
2. **Start the EHR Server**: `cd webapp && node app.js` (Terminal 1)
3. **Start the Sentinel**: `source .venv/bin/activate && python3 live_sentinel.py` (Terminal 2)
4. **Launch an Attack**: `source .venv/bin/activate && python3 attack_scripts/exfiltration.py` (Terminal 3)
5. **View the Dashboard**: `python3 dashboard.py` and open `http://localhost:5001` (Terminal 4)

## Technologies Used

| Technology | Purpose |
|------------|---------|
| **Python** | Core agent backend |
| **scikit-learn** | Machine learning ensemble models |
| **HistGradientBoosting** | High-performance gradient boosting classification |
| **SHAP** | Explainable AI visualizations |
| **Node.js / Express** | Target hospital EHR web server simulation |
| **Telegram API** | Zero-cost mobile admin alerts |
| **SHA-256** | Cryptographic hash chaining for audit ledger |
| **Flask** | Live threat dashboard serving |

## Security Architecture

1. **Target Monitoring**: Passive log tailing ensures zero performance hit on the main DB.
2. **Feature Extraction**: Groups raw requests by IP, mapping network anomalies to ML features.
3. **AI Ensemble Scoring**: 5 calibrated models compute a weighted threat score and confidence interval.
4. **Self-Healing & Containment**: Enforces Blast Radius constraints. High-tier threats trigger immediate containment (throttling, snapshots) but require human-in-the-loop authorization to fully lock down an admin account.

## Limitations and Future Work

Please see `FUTURE_WORK.md` for a comprehensive list of architectural limitations (such as IP spoofing, single-node blockchain, and cloud dependencies) and our planned mitigations.
