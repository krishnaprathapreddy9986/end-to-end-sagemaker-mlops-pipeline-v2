import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.pipeline import get_pipeline


<<<<<<< HEAD
=======
def parse_args():
    parser = argparse.ArgumentParser(description="Deploy or run the SageMaker lab pipeline.")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    parser.add_argument("--role-arn", default=os.getenv("SAGEMAKER_ROLE_ARN"))
    parser.add_argument("--model-bucket", default=os.getenv("MODEL_BUCKET"))
    parser.add_argument("--mlflow-tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", ""))
    parser.add_argument("--pipeline-name", default=os.getenv("PIPELINE_NAME", "sagemaker-mlops-lab"))
    parser.add_argument("--start", action="store_true", help="Start an execution after upsert.")
    return parser.parse_args()


>>>>>>> c32b77f62404591bdd5e89f094cd9a7263b02196
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