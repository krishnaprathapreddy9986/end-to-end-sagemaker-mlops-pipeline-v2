import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.train import save_lambda_model, train


def test_training_creates_lambda_model(tmp_path):
    model, metrics = train(test_size=0.2)
    save_lambda_model(model, metrics, tmp_path)

    model_file = Path(tmp_path) / "model.json"
    assert model_file.exists()
    assert metrics["mae_lakhs"] >= 0.0
