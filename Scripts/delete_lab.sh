#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
PROJECT="${PROJECT:-sagemaker-mlops-lab}"
ACCOUNT_ID="${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
MODEL_BUCKET="${MODEL_BUCKET:-$PROJECT-models-$ACCOUNT_ID}"
FRONTEND_BUCKET="${FRONTEND_BUCKET:-$PROJECT-frontend-$ACCOUNT_ID}"
PIPELINE_NAME="${PIPELINE_NAME:-$PROJECT}"
MODEL_PACKAGE_GROUP_NAME="${MODEL_PACKAGE_GROUP_NAME:-$PROJECT-models}"
DELETE_GITHUB_OIDC_PROVIDER="${DELETE_GITHUB_OIDC_PROVIDER:-false}"

echo "This will delete the SageMaker MLOps lab resources in $AWS_REGION:"
echo "- SageMaker pipeline: $PIPELINE_NAME"
echo "- SageMaker model package group: $MODEL_PACKAGE_GROUP_NAME"
echo "- Lambda function: $PROJECT-inference"
echo "- API Gateway: $PROJECT-api"
echo "- EC2 MLflow instances tagged Name=$PROJECT-mlflow"
echo "- Security group: $PROJECT-mlflow-sg"
echo "- S3 buckets: $MODEL_BUCKET, $FRONTEND_BUCKET"
echo "- IAM roles: $PROJECT-sagemaker-exec, $PROJECT-github-actions, $PROJECT-lambda"
echo
read -r -p "Type DELETE to continue: " CONFIRM
if [ "$CONFIRM" != "DELETE" ]; then
  echo "Cleanup cancelled."
  exit 0
fi

echo "Deleting SageMaker pipeline..."
aws sagemaker delete-pipeline \
  --region "$AWS_REGION" \
  --pipeline-name "$PIPELINE_NAME" >/dev/null 2>&1 || true

echo "Deleting SageMaker model packages..."
MODEL_PACKAGE_ARNS=$(aws sagemaker list-model-packages \
  --region "$AWS_REGION" \
  --model-package-group-name "$MODEL_PACKAGE_GROUP_NAME" \
  --query "ModelPackageSummaryList[].ModelPackageArn" \
  --output text 2>/dev/null || true)
for ARN in $MODEL_PACKAGE_ARNS; do
  aws sagemaker delete-model-package \
    --region "$AWS_REGION" \
    --model-package-name "$ARN" >/dev/null 2>&1 || true
done

echo "Deleting SageMaker model package group..."
aws sagemaker delete-model-package-group \
  --region "$AWS_REGION" \
  --model-package-group-name "$MODEL_PACKAGE_GROUP_NAME" >/dev/null 2>&1 || true

echo "Deleting Lambda function..."
aws lambda delete-function \
  --region "$AWS_REGION" \
  --function-name "$PROJECT-inference" >/dev/null 2>&1 || true

echo "Deleting API Gateway..."
API_IDS=$(aws apigatewayv2 get-apis \
  --region "$AWS_REGION" \
  --query "Items[?Name=='$PROJECT-api'].ApiId" \
  --output text 2>/dev/null || true)
for API_ID in $API_IDS; do
  aws apigatewayv2 delete-api \
    --region "$AWS_REGION" \
    --api-id "$API_ID" >/dev/null 2>&1 || true
done

echo "Terminating MLflow EC2 instances..."
INSTANCE_IDS=$(aws ec2 describe-instances \
  --region "$AWS_REGION" \
  --filters "Name=tag:Name,Values=$PROJECT-mlflow" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query "Reservations[].Instances[].InstanceId" \
  --output text 2>/dev/null || true)
if [ -n "$INSTANCE_IDS" ]; then
  aws ec2 terminate-instances \
    --region "$AWS_REGION" \
    --instance-ids $INSTANCE_IDS >/dev/null
  aws ec2 wait instance-terminated \
    --region "$AWS_REGION" \
    --instance-ids $INSTANCE_IDS
fi

echo "Deleting MLflow security group..."
VPC_ID=$(aws ec2 describe-vpcs \
  --region "$AWS_REGION" \
  --filters Name=isDefault,Values=true \
  --query "Vpcs[0].VpcId" \
  --output text 2>/dev/null || true)
SG_ID=$(aws ec2 describe-security-groups \
  --region "$AWS_REGION" \
  --filters "Name=group-name,Values=$PROJECT-mlflow-sg" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" \
  --output text 2>/dev/null || true)
if [ "$SG_ID" != "None" ] && [ -n "$SG_ID" ]; then
  aws ec2 delete-security-group \
    --region "$AWS_REGION" \
    --group-id "$SG_ID" >/dev/null 2>&1 || true
fi

echo "Emptying and deleting S3 buckets..."
for BUCKET in "$MODEL_BUCKET" "$FRONTEND_BUCKET"; do
  if aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
    aws s3 rm "s3://$BUCKET" --recursive >/dev/null 2>&1 || true
    aws s3 rb "s3://$BUCKET" >/dev/null 2>&1 || true
  fi
done

echo "Deleting IAM roles and policies..."
aws iam detach-role-policy \
  --role-name "$PROJECT-sagemaker-exec" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess >/dev/null 2>&1 || true
aws iam delete-role-policy \
  --role-name "$PROJECT-sagemaker-exec" \
  --policy-name "$PROJECT-sagemaker-s3" >/dev/null 2>&1 || true
aws iam delete-role \
  --role-name "$PROJECT-sagemaker-exec" >/dev/null 2>&1 || true

aws iam delete-role-policy \
  --role-name "$PROJECT-github-actions" \
  --policy-name "$PROJECT-github-actions-policy" >/dev/null 2>&1 || true
aws iam detach-role-policy \
  --role-name "$PROJECT-github-actions" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess >/dev/null 2>&1 || true
aws iam delete-role \
  --role-name "$PROJECT-github-actions" >/dev/null 2>&1 || true

aws iam detach-role-policy \
  --role-name "$PROJECT-lambda" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole >/dev/null 2>&1 || true
aws iam delete-role-policy \
  --role-name "$PROJECT-lambda" \
  --policy-name "$PROJECT-lambda-s3-read" >/dev/null 2>&1 || true
aws iam delete-role \
  --role-name "$PROJECT-lambda" >/dev/null 2>&1 || true

if [ "$DELETE_GITHUB_OIDC_PROVIDER" = "true" ]; then
  echo "Deleting GitHub OIDC provider..."
  aws iam delete-open-id-connect-provider \
    --open-id-connect-provider-arn "arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com" >/dev/null 2>&1 || true
else
  echo "Keeping GitHub OIDC provider. Set DELETE_GITHUB_OIDC_PROVIDER=true to delete it."
fi

echo "Cleanup complete."
