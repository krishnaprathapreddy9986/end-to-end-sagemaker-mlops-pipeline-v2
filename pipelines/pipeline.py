from pathlib import Path

import boto3
import sagemaker
from sagemaker import image_uris
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.workflow.parameters import ParameterFloat, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import TrainingStep
from sagemaker.session import Session


BASE_DIR = Path(__file__).resolve().parents[1]


def get_pipeline(
    region: str,
    role_arn: str,
    model_bucket: str,
    mlflow_tracking_uri: str = "",
    pipeline_name: str = "sagemaker-mlops-lab",
):

    # ✅ Correct session
    boto_session = boto3.Session(region_name=region)
    session = Session(boto_session=boto_session)

    # -------------------------
    # Parameters
    # -------------------------
    test_size = ParameterFloat(name="TestSize", default_value=0.2)
    training_instance = ParameterString(
        name="TrainingInstanceType", default_value="ml.m5.large"
    )

    # -------------------------
    # Training image
    # -------------------------
    sklearn_image = image_uris.retrieve(
        framework="sklearn",
        region=region,
        version="1.2-1",
        py_version="py3",
    )

    # -------------------------
    # Environment
    # -------------------------
    training_environment = {
        "MLFLOW_EXPERIMENT_NAME": "hyderabad-house-price-lab",
    }

    if mlflow_tracking_uri:
        training_environment["MLFLOW_TRACKING_URI"] = mlflow_tracking_uri

    # -------------------------
    # Estimator
    # -------------------------
    estimator = SKLearn(
        entry_point="train.py",
        source_dir=str(BASE_DIR / "src"),
        role=role_arn,
        image_uri=sklearn_image,
        instance_count=1,
        instance_type="ml.m5.large",
        sagemaker_session=session,
        output_path=f"s3://{model_bucket}/artifacts",
        hyperparameters={
            "test-size": "0.2"
        },
        environment=training_environment,
    )

    # -------------------------
    # Training Step ONLY
    # -------------------------
    train_step = TrainingStep(
        name="TrainHyderabadHousePriceModel",
        estimator=estimator,
    )

    # -------------------------
    # PIPELINE (NO MODEL REGISTRY)
    # -------------------------
    pipeline = Pipeline(
        name=pipeline_name,
        parameters=[test_size, training_instance],
        steps=[train_step],
        sagemaker_session=session,
    )

    return pipeline