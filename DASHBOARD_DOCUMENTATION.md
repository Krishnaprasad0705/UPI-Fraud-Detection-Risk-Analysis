# UPI Fraud Detection Dashboard v2.2 - FULLY FIXED ✅

## 🎯 QUICK START
```
double-click run_dashboard.bat → http://localhost:5000
```

## 🚀 Features
- **4 Charts**: Risk Pie (`/api/stats`), Trend Line, **Hour Bar** (`/api/hourly_fraud`), **Location Bar** (`/api/location_risk`)
- **CSV Export** (`/api/export_risk_csv?status=BLOCK/REVIEW`): ID,Customer,Amount,Hr,Location,Device,Risk%,Status,**Reasons**,Time
- **Live**: 5s refresh stats/alerts/table
- **Neon UI**: Responsive, error-proof

## Data: Run streaming (`python start_streaming.py`)
- Realistic: 3% BLOCK (>70%), 7% REVIEW (30-70%)
- Charts populate ~10s

## Endpoints Used
| API | Purpose |
|-----|---------|
| /api/stats | Pie/metrics |
| /api/alerts | Live table |
| /api/hourly_fraud | Hour chart |
| /api/location_risk | Location chart |
| /api/export_risk_csv | Downloads |

**Status: COMPLETE - All charts/exports working! Reload browser.**
- **4 Interactive Charts** (Chart.js):
  | Chart | Description | Data Source |
  |-------|-------------|-------------|
  | Risk Pie | Safe/Review/Block distribution | `/api/stats` |
  | Trend Line | Txns over time | Live DB |
  | **Fraud by Hour Bar** | BLOCK/review per hour (0-23) | DB transaction_hour |
  | **Risk by Location Bar** | Top cities for risk txns | DB location |

- **CSV Export for Risk Txns** (New `/api/export_risk_csv`):
  - **BLOCK CSV**: High-risk (>70%) w/ reasons
  - **Review CSV**: Medium-risk (30-70%) w/ reasons
  - **Columns**: ID, Customer_ID, Amount_₹, Hour, Location, Device, Risk_Score_%, Status, **Reasons** (triggered_rules e.g. "High Amount, Foreign"), Timestamp
  - Buttons: "Export BLOCK CSV" | "Export Review CSV"

## 📊 Live Status
- **localhost:5000**: Auto-refresh 5s (stats, alerts, table)
- **Charts render empty?** Run `python start_streaming.py` for data.
- **API Logs**: Active (/stats, /alerts, /recent_transactions)

## 🔧 Usage
1. Start streaming: `python start_streaming.py`
2. Open dashboard: **localhost:5000**
3. Click **Export BLOCK CSV** / **Review CSV** → Download w/ reasons.

**Realistic Rates**: 3% BLOCK, 7% Review → CSV exports ~100 rows/1k txns w/ exact reasons.

**Complete** - Reload page to see all graphs + working CSV export.

