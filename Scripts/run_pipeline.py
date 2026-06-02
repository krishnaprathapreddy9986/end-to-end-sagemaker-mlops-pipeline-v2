import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.pipeline import get_pipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Deploy or run the SageMaker lab pipeline.")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--role-arn", default=os.getenv("SAGEMAKER_ROLE_ARN"))
    parser.add_argument("--model-bucket", default=os.getenv("MODEL_BUCKET"))
    parser.add_argument("--mlflow-tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", ""))
    parser.add_argument("--pipeline-name", default=os.getenv("PIPELINE_NAME", "sagemaker-mlops-lab"))
    parser.add_argument("--start", action="store_true", help="Start an execution after upsert.")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.role_arn:
        raise SystemExit("Missing --role-arn or SAGEMAKER_ROLE_ARN.")
    if not args.model_bucket:
        raise SystemExit("Missing --model-bucket or MODEL_BUCKET.")

    pipeline = get_pipeline(
        region=args.region,
        role_arn=args.role_arn,
        model_bucket=args.model_bucket,
        mlflow_tracking_uri=args.mlflow_tracking_uri,
        pipeline_name=args.pipeline_name,
    )
    pipeline.upsert(role_arn=args.role_arn)
    print(f"Upserted pipeline: {args.pipeline_name}")

    if args.start:
        execution = pipeline.start()
        print(f"Started execution: {execution.arn}")


if __name__ == "__main__":
    main()
