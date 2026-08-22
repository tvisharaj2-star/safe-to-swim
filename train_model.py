import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

df = pd.read_excel("combine_data.xlsx")
df.columns = df.columns.str.strip()

df = df.dropna(subset = ["hightoday"])
df["unsafe"] = df["hightoday"].astype(int)

features = ["rain_1d", "rain_3d", "rain_7d", "watertempc", "geomean30d", "nsampleshigh30d"]
data = df.dropna(subset=features)
X = data[features]
y = data["unsafe"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42)
model.fit(X_train, y_train)

probs = model.predict_proba(X_test)[:, 1]
pred = (probs > 0.30).astype(int)
print(classification_report(y_test, pred, target_names=["Safe", "Unsafe"]))

joblib.dump(model, "model.pkl")
print("Model saved as model.pkl")