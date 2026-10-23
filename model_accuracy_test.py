import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from fraud_detection_system import MLFraudDetector, pd, np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
import warnings
warnings.filterwarnings('ignore')

print('Generating 20,000 synthetic UPI fraud dataset (98% safe, 2% fraud)...')

n_samples = 20000
np.random.seed(42)  # Reproducible

data = pd.DataFrame({
    'transaction_amount': np.random.exponential(3000, n_samples).clip(10, 100000),
    'transaction_hour': np.random.randint(0, 24, n_samples),
    'is_foreign_transaction': np.random.choice([0,1], n_samples, p=[0.95, 0.05]),
    'failed_login_attempts': np.random.poisson(0.1, n_samples),
    'account_tenure_years': np.random.exponential(3, n_samples).clip(0, 20),
    'device_risk': np.random.uniform(0, 20, n_samples),
    'behavioral_anomaly': np.random.uniform(0, 30, n_samples),
    'velocity_score': np.random.poisson(1, n_samples) * 10,
    'reputation_score': np.random.normal(90, 10, n_samples).clip(0, 100),
})

# Inject fraud signals (rare but high-risk patterns)
fraud_indices = np.random.choice(n_samples, size=int(0.02 * n_samples), replace=False)
data.loc[fraud_indices, 'transaction_amount'] *= np.random.uniform(3, 10)
data.loc[fraud_indices, 'transaction_hour'] = np.random.choice([0,1,2,22,23], size=len(fraud_indices))
data.loc[fraud_indices, 'is_foreign_transaction'] = 1
data.loc[fraud_indices, 'failed_login_attempts'] += np.random.poisson(2, len(fraud_indices))
data.loc[fraud_indices, 'device_risk'] += np.random.uniform(10, 30)
data.loc[fraud_indices, 'behavioral_anomaly'] += np.random.uniform(20, 50)
data.loc[fraud_indices, 'reputation_score'] -= np.random.uniform(20, 50)

data['is_fraud'] = 0
data.loc[fraud_indices, 'is_fraud'] = 1

print(f'Dataset: {len(data):,} samples, Fraud rate: {data["is_fraud"].mean():.2%}')

# Train ML Model
detector = MLFraudDetector()
accuracy = detector.train_model(data)
if accuracy is None:
    raise SystemExit('PyTorch is required. Install dependencies with: pip install -r requirements.txt')
print(f'\n✅ Holdout Accuracy: {accuracy:.2%}')

# Detailed Metrics
X = data[detector.feature_names].fillna(0)
y = data['is_fraud']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
X_test_scaled = detector.scaler.transform(X_test)

# PyTorch models expose logits rather than sklearn predict/predict_proba.
import torch
detector.model.eval()
with torch.no_grad():
    y_proba = torch.sigmoid(detector.model(torch.tensor(X_test_scaled, dtype=torch.float32, device=detector.device))).cpu().numpy().ravel()
y_pred = (y_proba >= 0.5).astype(int)

print('\n📊 Classification Report:')
print(classification_report(y_test, y_pred, target_names=['Safe', 'Fraud']))

print(f'\n🎯 ROC-AUC: {roc_auc_score(y_test, y_proba):.4f}')
print('\nFeature importance is represented by learned neural-network weights; use SHAP or permutation importance for production explanations.')

print('\nModel ready for production use. Run: python fraud_detection_api_new.py')
