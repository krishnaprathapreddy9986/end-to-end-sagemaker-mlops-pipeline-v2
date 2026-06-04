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

    pipeline = get_pipeline(
        region=region,
        role_arn=role_arn,
        model_bucket=model_bucket,
        pipeline_name=pipeline_name,
    )

    pipeline.upsert(role_arn=role_arn)
    print(f"Pipeline upserted: {pipeline_name}")

    execution = pipeline.start()
    print("Pipeline execution started:", execution.arn)


if __name__ == "__main__":
    main()