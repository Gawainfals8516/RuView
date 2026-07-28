import pandas as pd
import numpy as np
import argparse
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

def extract_features(df, window_size=20):
    """
    Extracts features from the raw time-series data using a sliding window approach.
    Since ESP32 sends a metric every ~1s (100 attempts at 10ms), a window size of 5
    means looking at 5 seconds of historical data.
    """
    features = []
    labels = []

    # We group by the material label first to ensure windows don't cross boundaries of different recordings
    for label, group in df.groupby('material_label'):
        # Reset index to iterate smoothly
        group = group.reset_index(drop=True)

        # Slide a window across the group
        for i in range(len(group) - window_size + 1):
            window = group.iloc[i:i+window_size]

            success_rates = window['success_rate_pct'].values
            latencies = window['avg_latency_us'].values

            # Feature: Success Rate Drop metrics
            sr_mean = np.mean(success_rates)
            sr_min = np.min(success_rates)
            sr_var = np.var(success_rates)

            # Feature: Latency metrics
            lat_mean = np.mean(latencies)
            lat_max = np.max(latencies)
            lat_var = np.var(latencies)

            # Feature: Latency Decay Slope (Linear regression slope over time)
            # x is just the indices 0 to window_size-1
            x = np.arange(window_size)
            if len(set(latencies)) > 1: # Avoid polyfit warnings on flat data
                slope, _ = np.polyfit(x, latencies, 1)
            else:
                slope = 0.0

            features.append({
                'sr_mean': sr_mean,
                'sr_min': sr_min,
                'sr_var': sr_var,
                'lat_mean': lat_mean,
                'lat_max': lat_max,
                'lat_var': lat_var,
                'lat_slope': slope
            })
            labels.append(label)

    return pd.DataFrame(features), np.array(labels)

def main():
    parser = argparse.ArgumentParser(description="Train Dielectric ML Classifier")
    parser.add_argument("data_csv", help="Path to the ml_training_data.csv file")
    parser.add_argument("--window", type=int, default=5, help="Sliding window size (default: 5 samples)")
    args = parser.parse_args()

    print(f"Loading data from {args.data_csv}...")
    try:
        df = pd.read_csv(args.data_csv)
    except FileNotFoundError:
        print(f"Error: Could not find {args.data_csv}. Did you run ml_data_collector.py first?")
        return

    # Basic cleaning
    df = df.dropna()

    print(f"Extracting sliding window features (Window size: {args.window})...")
    X, y = extract_features(df, window_size=args.window)

    if len(X) == 0:
        print("Error: Not enough data points to extract features. Record longer sessions.")
        return

    print(f"Extracted {len(X)} feature windows.")
    print("Splitting dataset into train/test sets...")

    # Stratified split to keep label proportions
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("Training Random Forest Classifier...")
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)

    print("\n--- Model Evaluation ---")
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {acc * 100:.2f}%")

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    print("\nFeature Importances:")
    importances = clf.feature_importances_
    for feature, imp in zip(X.columns, importances):
        print(f"  - {feature}: {imp:.4f}")

    # Save Model
    model_filename = 'nfc_dielectric_model.pkl'
    joblib.dump(clf, model_filename)
    print(f"\nModel successfully saved to {model_filename}")

if __name__ == "__main__":
    main()
