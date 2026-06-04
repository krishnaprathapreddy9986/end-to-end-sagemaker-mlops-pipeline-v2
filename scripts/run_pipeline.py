import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.pipeline import get_pipeline


def main():
    region = os.getenv("AWS_REGION", "ap-south-1")
    role_arn = os.getenv("SAGEMAKER_ROLE_ARN")
    model_bucket = os.getenv("MODEL_BUCKET")
    pipeline_name = os.getenv("PIPELINE_NAME", "sagemaker-mlops-lab")

    print(f"🚀 Region: {region}")
    print(f"📦 Pipeline Name: {pipeline_name}")

    if not role_arn:
        raise ValueError("Missing SAGEMAKER_ROLE_ARN")
    if not model_bucket:
        raise ValueError("Missing MODEL_BUCKET")

    # 1. Build pipeline definition
    pipeline = get_pipeline(
        region=region,
        role_arn=role_arn,
        model_bucket=model_bucket,
        pipeline_name=pipeline_name,
    )

    print("🔧 Creating / updating SageMaker pipeline...")

    # 2. Upsert pipeline (creates definition in AWS)
    upsert_response = pipeline.upsert(role_arn=role_arn)
    print("✅ Pipeline upserted successfully")
    print(f"📄 Upsert response: {upsert_response}")

    # 3. START PIPELINE EXECUTION (THIS ACTUALLY RUNS TRAINING)
    print("🚀 Starting pipeline execution...")

    execution = pipeline.start()

    print("🎯 Pipeline execution started successfully!")
    print(f"📌 Execution ARN: {execution.arn}")


if __name__ == "__main__":
    main()