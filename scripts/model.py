import pandas as pd
import random
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report

# ----------------------------
# 1. Load data
# ----------------------------
df = pd.read_csv("../data/processed/all_matches_dataset.csv")

# ----------------------------
# 2. Drop columns we don't want for ML
# ----------------------------
drop_cols = ["match_date"]  # keep for reference in dataset, but not for training
df = df.drop(columns=drop_cols, errors="ignore")

# ----------------------------
# 3. Set target
# ----------------------------
y = df["runs_scored"]

# ----------------------------
# 4. Set features
# ----------------------------
X = df.drop(columns=["runs_scored"])

# ----------------------------
# 5. Label encode categorical columns
#    (safer than one-hot for player names)
# ----------------------------
label_encoders = {}

categorical_cols = X.select_dtypes(include=["object"]).columns

for col in categorical_cols:
    le = LabelEncoder()
    X[col] = le.fit_transform(X[col].astype(str))
    label_encoders[col] = le

# ----------------------------
# 6. Train-test split
# ----------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ----------------------------
# 7. Train model
# ----------------------------
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)

# ----------------------------
# 8. Evaluate model
# ----------------------------
y_pred = model.predict(X_test)

print("\n==============================")
print("MODEL EVALUATION")
print("==============================")
print("Accuracy:", accuracy_score(y_test, y_pred))
print("\nClassification Report:")
print(classification_report(y_test, y_pred, zero_division=0))

# ----------------------------
# 9. Sample 6 random deliveries
# ----------------------------
sample_size = min(6, len(X_test))
random_indices = random.sample(range(len(X_test)), sample_size)

print("\n==============================")
print("RANDOM SAMPLE PREDICTIONS")
print("==============================")

for idx in random_indices:
    X_row = X_test.iloc[idx:idx+1]

    # original readable row from the full dataframe
    original_row = df.iloc[X_test.index[idx]]

    pred = model.predict(X_row)[0]
    actual = y_test.iloc[idx]

    print("\n------------------------------")
    print("Match State:")
    print(original_row)

    print("\nPrediction:", pred)
    print("Actual:", actual)

    # optional: show class probabilities
    probs = model.predict_proba(X_row)[0]
    print("\nProbabilities:")
    for run_value, prob in zip(model.classes_, probs):
        print(f"Runs={run_value}: {prob:.3f}")