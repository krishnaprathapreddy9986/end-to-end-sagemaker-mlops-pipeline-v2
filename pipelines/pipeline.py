from pathlib import Path

import sagemaker
from sagemaker import image_uris
from sagemaker.model import Model
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.workflow.model_step import ModelStep
from sagemaker.workflow.parameters import ParameterFloat, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import PipelineSession
from sagemaker.workflow.steps import TrainingStep


BASE_DIR = Path(__file__).resolve().parents[1]


def get_pipeline(
    region: str,
    role_arn: str,
    model_bucket: str,
    mlflow_tracking_uri: str = "",
    pipeline_name: str = "sagemaker-mlops-lab",
):
    session = PipelineSession(
        boto_session=sagemaker.session.boto3.Session(region_name=region)
    )

    test_size = ParameterFloat(name="TestSize", default_value=0.2)
    training_instance = ParameterString(
        name="TrainingInstanceType", default_value="ml.m5.large"
    )

    sklearn_image = image_uris.retrieve(
        framework="sklearn",
        region=region,
        version="1.2-1",
        py_version="py3",
    )

    training_environment = {
        "MLFLOW_EXPERIMENT_NAME": "hyderabad-house-price-lab",
    }
    if mlflow_tracking_uri:
        training_environment["MLFLOW_TRACKING_URI"] = mlflow_tracking_uri

    estimator = SKLearn(
        entry_point="train.py",
        source_dir=str(BASE_DIR / "src"),
        role=role_arn,
        image_uri=sklearn_image,
        instance_count=1,
        instance_type=training_instance,
        sagemaker_session=session,
        output_path=f"s3://{model_bucket}/artifacts",
        hyperparameters={
            "test-size": test_size,
        },
        environment=training_environment,
    )

    train_step = TrainingStep(
        name="TrainHyderabadHousePriceModel",
        estimator=estimator,
    )

    model = Model(
        image_uri=sklearn_image,
        model_data=train_step.properties.ModelArtifacts.S3ModelArtifacts,
        role=role_arn,
        sagemaker_session=session,
    )

    register_args = model.register(
        content_types=["application/json"],
        response_types=["application/json"],
        inference_instances=["ml.m5.large"],
        transform_instances=["ml.m5.large"],
        model_package_group_name=f"{pipeline_name}-models",
        approval_status="PendingManualApproval",
    )

    register_step = ModelStep(
        name="RegisterModelPackage",
        step_args=register_args,
    )

    return Pipeline(
        name=pipeline_name,
        parameters=[test_size, training_instance],
        steps=[train_step, register_step],
        sagemaker_session=session,
    )
