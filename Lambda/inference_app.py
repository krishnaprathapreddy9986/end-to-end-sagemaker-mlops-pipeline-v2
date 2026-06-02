import json
import os
import tarfile
import tempfile
from pathlib import Path

import boto3


MODEL_CACHE = None


def _download_model():
    bucket = os.environ["MODEL_BUCKET"]
    key = os.environ["MODEL_KEY"]

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "model.tar.gz"
        boto3.client("s3").download_file(bucket, key, str(archive_path))
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extract("model.json", path=tmpdir)
        return json.loads((Path(tmpdir) / "model.json").read_text(encoding="utf-8"))


def _get_model():
    global MODEL_CACHE
    if MODEL_CACHE is None:
        MODEL_CACHE = _download_model()
    return MODEL_CACHE


def _predict(features, model):
    estimate = sum(w * x for w, x in zip(model["coef"], features)) + model["intercept"]
    return {
        "problem": model["problem"],
        "estimated_price_lakhs": round(estimate, 2),
        "estimated_price_inr": round(estimate * 100000, 2),
        "feature_names": model["feature_names"],
        "features": features,
    }


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        features = body.get("features")
        if not isinstance(features, list) or len(features) != 5:
            return _response(
                400,
                {
                    "error": "Send JSON like {'features':[1200,3,2,5,8]} for square_feet, bedrooms, bathrooms, property_age, distance_to_hitech_city_km."
                },
            )

        prediction = _predict([float(value) for value in features], _get_model())
        return _response(200, prediction)
    except Exception as exc:
        return _response(500, {"error": str(exc)})


def _response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": "*",
        },
        "body": json.dumps(payload),
    }
