import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.pipeline import get_pipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Deploy or run the SageMaker pipeline")

    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--role-arn", default=os.getenv("SAGEMAKER_ROLE_ARN"))
    parser.add_argument("--model-bucket", default=os.getenv("MODEL_BUCKET"))
    parser.add_argument("--mlflow-tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", ""))
    parser.add_argument("--pipeline-name", default=os.getenv("PIPELINE_NAME", "sagemaker-mlops-lab"))
    parser.add_argument("--start", action="store_true", help="Start pipeline after upsert")

    return parser.parse_args()


def validate(args):
    if not args.role_arn:
        raise ValueError("Missing role ARN: set --role-arn or SAGEMAKER_ROLE_ARN")
    if not args.model_bucket:
        raise ValueError("Missing model bucket: set --model-bucket or MODEL_BUCKET")


def main():
    args = parse_args()
    validate(args)

    print("🚀 Pipeline Configuration")
    print(f"Region      : {args.region}")
    print(f"Role ARN    : {args.role_arn}")
    print(f"Bucket      : {args.model_bucket}")
    print(f"Pipeline    : {args.pipeline_name}")
    print(f"MLflow URI  : {args.mlflow_tracking_uri}")

    pipeline = get_pipeline(
        region=args.region,
        role_arn=args.role_arn,
        model_bucket=args.model_bucket,
        mlflow_tracking_uri=args.mlflow_tracking_uri,
        pipeline_name=args.pipeline_name,
    )

    pipeline.upsert(role_arn=args.role_arn)
    print(f"✅ Pipeline upserted: {args.pipeline_name}")

    if args.start:
        execution = pipeline.start()
        print(f"🚀 Execution started: {execution.arn}")
    else:
        print("ℹ️ Upsert complete. Use --start to run execution.")


if __name__ == "__main__":
    main()
