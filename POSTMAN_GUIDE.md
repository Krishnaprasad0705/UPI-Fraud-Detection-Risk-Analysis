# Postman Collection for UPI Fraud Detection API

## 📋 **Postman Setup Instructions**

### **Step 1: Create New Collection**
1. Open Postman
2. Click **"New"** → **"Collection"**
3. Name it: `UPI Fraud Detection API`
4. Set base URL: `http://127.0.0.1:5000`

### **Step 2: Add Environment Variables**
Create environment called `UPI Fraud Detection`:
- `base_url`: `http://127.0.0.1:5000`
- `customer_id`: `user123` (for testing)

---

## 🔍 **API Endpoints & Sample Requests**

### **1. Health Check**
```
Method: GET
URL: {{base_url}}/health
```
**Expected Response:**
```json
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "version": "2.1"
}
```

### **2. Get Live Statistics**
```
Method: GET
URL: {{base_url}}/api/stats
```
**Expected Response:**
```json
{
    "total_transactions": 1000,
    "safe_transactions": 600,
    "review_transactions": 200,
    "blocked_transactions": 200,
    "fraud_rate": 20.0,
    "processing_rate": 19.7
}
```

### **3. Analyze Single Transaction (MOST IMPORTANT)**
```
Method: POST
URL: {{base_url}}/api/analyze
Headers:
  Content-Type: application/json

Body (raw JSON):
```
```json
{
    "customer_id": "user123",
    "transaction_amount": 25000.00,
    "transaction_time": "2024-01-15T14:30:00Z",
    "payment_method": "UPI",
    "merchant_category": "Electronics",
    "device_type": "Android",
    "location": "Mumbai",
    "is_foreign_transaction": 0,
    "failed_login_attempts": 0,
    "account_tenure_years": 2
}
```
**Expected Response:**
```json
{
    "transaction_id": 12345,
    "customer_id": "user123",
    "risk_score": 45.67,
    "classification": "REVIEW",
    "is_fraud": 0,
    "triggered_rules": "High Amount",
    "analysis_time_ms": 15.2
}
```

### **4. Batch Analyze Transactions**
```
Method: POST
URL: {{base_url}}/api/batch_analyze
Headers:
  Content-Type: application/json

Body (raw JSON):
```
```json
{
    "transactions": [
        {
            "customer_id": "user123",
            "transaction_amount": 500.00,
            "merchant_category": "Grocery",
            "device_type": "Android",
            "location": "Delhi"
        },
        {
            "customer_id": "user456",
            "transaction_amount": 75000.00,
            "merchant_category": "Electronics",
            "device_type": "Web",
            "location": "Mumbai"
        }
    ]
}
```
**Expected Response:**
```json
{
    "results": [...],
    "count": 2,
    "summary": {
        "approved": 1,
        "review": 0,
        "blocked": 1
    }
}
```

### **5. Get Fraud Alerts**
```
Method: GET
URL: {{base_url}}/api/alerts
```
**Expected Response:**
```json
[
    {
        "alert_id": 1,
        "transaction_id": 12345,
        "customer_id": "user123",
        "risk_score": 85.5,
        "classification": "BLOCK",
        "reasons": "High Amount, Unusual Time",
        "timestamp": "2024-01-15T14:30:00Z"
    }
]
```

### **6. Get Customer Profile**
```
Method: GET
URL: {{base_url}}/api/customer/{{customer_id}}/profile
```
**Expected Response:**
```json
{
    "customer_id": "user123",
    "avg_transaction_amount": 1250.50,
    "common_hour": 14,
    "common_location": "Mumbai",
    "common_device": "Android",
    "transaction_count": 45,
    "last_transaction_time": "2024-01-15T14:30:00Z"
}
```

### **7. Simulate Transaction**
```
Method: POST
URL: {{base_url}}/api/simulate_transaction
Headers:
  Content-Type: application/json

Body (raw JSON):
```
```json
{
    "customer_id": "test_user",
    "amount": 10000.00,
    "location": "Bangalore",
    "device": "iOS"
}
```

### **8. Export Risk CSV**
```
Method: GET
URL: {{base_url}}/api/export_risk_csv?status=BLOCK
```
**Note:** This will download a CSV file with blocked transactions.

---

## 🧪 **Testing Scenarios**

### **High-Risk Transaction Test:**
Use these values to trigger BLOCK classification:
```json
{
    "customer_id": "fraud_user",
    "transaction_amount": 75000.00,
    "transaction_time": "2024-01-15T03:00:00Z",
    "device_type": "Web",
    "location": "London",
    "is_foreign_transaction": 1,
    "failed_login_attempts": 5,
    "account_tenure_years": 0
}
```

### **Low-Risk Transaction Test:**
```json
{
    "customer_id": "safe_user",
    "transaction_amount": 500.00,
    "transaction_time": "2024-01-15T14:00:00Z",
    "device_type": "Android",
    "location": "Mumbai",
    "is_foreign_transaction": 0,
    "failed_login_attempts": 0,
    "account_tenure_years": 3
}
```

---

## 📊 **Postman Tips**

1. **Save Requests:** Save each request in your collection
2. **Set Environment:** Use `{{base_url}}` variable
3. **Test Scripts:** Add tests to validate responses
4. **Runner:** Use Collection Runner for batch testing
5. **History:** Check request history for debugging

## 🚀 **Quick Start:**

1. **Import this collection** into Postman
2. **Set environment** to `UPI Fraud Detection`
3. **Start your API server:** `python fraud_detection_api_new.py`
4. **Test endpoints** starting with `/health`
5. **Analyze transactions** using `/api/analyze`

Your API is now ready for comprehensive testing! 🎯