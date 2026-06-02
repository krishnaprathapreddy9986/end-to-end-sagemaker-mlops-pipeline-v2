import argparse
import json
import os
from pathlib import Path

import mlflow
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


FEATURES = [
    "square_feet",
    "bedrooms",
    "bathrooms",
    "property_age",
    "distance_to_hitech_city_km",
]
TARGET = "price_lakhs"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-size", type=float, default=0.2)
    return parser.parse_args()


def hyderabad_house_price_data():
    return pd.DataFrame(
        [
            [650, 1, 1, 8, 18, 42],
            [800, 2, 2, 6, 14, 58],
            [950, 2, 2, 4, 10, 72],
            [1100, 2, 2, 3, 8, 88],
            [1250, 3, 2, 5, 12, 95],
            [1400, 3, 3, 2, 7, 118],
            [1600, 3, 3, 1, 5, 145],
            [1800, 3, 3, 4, 9, 152],
            [2000, 4, 3, 2, 6, 188],
            [2200, 4, 4, 1, 4, 230],
            [2400, 4, 4, 0, 3, 275],
            [2800, 4, 4, 2, 5, 320],
            [3200, 5, 5, 1, 6, 410],
            [3600, 5, 5, 0, 4, 510],
            [4200, 5, 6, 1, 3, 680],
        ],
        columns=FEATURES + [TARGET],
    )


def train(test_size: float):
    data = hyderabad_house_price_data()
    x_train, x_test, y_train, y_test = train_test_split(
        data[FEATURES],
        data[TARGET],
        test_size=test_size,
        random_state=42,
    )

    model = LinearRegression()
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    metrics = {
        "mae_lakhs": float(mean_absolute_error(y_test, predictions)),
        "r2": float(r2_score(y_test, predictions)),
    }

    return model, metrics


def save_lambda_model(model, metrics: dict, model_dir: Path):
    model_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "problem": "Hyderabad house price prediction",
        "model_type": "linear_regression",
        "target": TARGET,
        "target_unit": "lakhs_inr",
        "feature_names": FEATURES,
        "coef": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "metrics": metrics,
    }
    (model_dir / "model.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def log_to_mlflow(test_size: float, metrics: dict):
    mlflow.set_experiment(
        os.getenv("MLFLOW_EXPERIMENT_NAME", "hyderabad-house-price-lab")
    )
    with mlflow.start_run():
        mlflow.log_param("problem", "Hyderabad house price prediction")
        mlflow.log_param("test_size", test_size)
        for name, value in metrics.items():
            mlflow.log_metric(name, value)


def main():
    args = parse_args()
    model, metrics = train(args.test_size)

    model_dir = Path(os.getenv("SM_MODEL_DIR", "model"))
    save_lambda_model(model, metrics, model_dir)
    log_to_mlflow(args.test_size, metrics)

    print(f"mae_lakhs={metrics['mae_lakhs']:.4f}")
    print(f"r2={metrics['r2']:.4f}")
    print(f"model_dir={model_dir}")


if __name__ == "__main__":
    main()
