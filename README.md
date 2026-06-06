# SageMaker MLOps S Lab

![MLOps SageMaker Project Diagram](sagemaker-mlops-project.png)

Problem statement: predict Hyderabad house prices using `square_feet`, `bedrooms`, `bathrooms`, `property_age`, and `distance_to_hitech_city_km`.

Flow: GitHub Actions -> AWS OIDC -> SageMaker training job -> MLflow on EC2 -> SageMaker Model Registry -> S3 model artifact -> Lambda -> API Gateway -> frontend.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
make validate
```

## AWS Infrastructure

No Terraform is used. Use AWS CLI commands below, and use `infra/README.md` for the full detailed guide.

For this student lab, default VPC is enough. You do not need a separate VPC for SageMaker and MLflow. MLflow runs on EC2 in the default VPC, and SageMaker can call the MLflow public URL if security group port `5000` allows access. For production, use private subnets, VPC endpoints, and tighter security.

That guide creates:

- MLflow tracking server on EC2.
- S3 bucket for model artifacts.
- SageMaker execution role.
- GitHub Actions OIDC role.
- Lambda inference function.
- API Gateway HTTP API.
- Optional S3 static frontend bucket.

## Correct Run Sequence

Follow this order only:

1. Create S3 model bucket.
2. Create SageMaker execution role.
3. Create MLflow EC2 and confirm `http://PUBLIC_IP:5000` opens.
4. Create or update GitHub OIDC role.
5. Add GitHub secret `AWS_GITHUB_ACTIONS_ROLE_ARN`.
6. Add GitHub variables `SAGEMAKER_ROLE_ARN`, `MODEL_BUCKET`, and `MLFLOW_TRACKING_URI`.
7. Run GitHub Actions to start SageMaker training.
8. Check SageMaker training job, Model Registry, MLflow experiment, and S3 model artifact.
9. Copy latest S3 `model.tar.gz` key.
10. Create or update Lambda with `MODEL_BUCKET` and `MODEL_KEY`.
11. Create API Gateway route `POST /predict`.
12. Test API Gateway.
13. Connect frontend.

## Quick AWS CLI And Console Steps

Set variables:

```bash
export AWS_REGION=ap-south-1
export PROJECT=sagemaker-mlops-lab
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export GITHUB_OWNER=YOUR_GITHUB_USER_OR_ORG
export GITHUB_REPO=YOUR_REPO_NAME
export MODEL_BUCKET=$PROJECT-models-$ACCOUNT_ID
export KEY_PAIR_NAME=mlops-user
```

Console:

1. Open AWS Console.
2. In the top-right region selector, choose `Asia Pacific (Mumbai) ap-south-1`.
3. Use the same region for EC2, SageMaker, Lambda, API Gateway, and S3.

Create S3 model bucket:

```bash
aws s3 mb s3://$MODEL_BUCKET --region $AWS_REGION
```

Console:

1. Search `S3`.
2. Go to `S3` -> `Buckets`.
3. Click `Create bucket`.
4. Bucket name: enter `sagemaker-mlops-lab-models-YOUR_ACCOUNT_ID`.
5. Region: choose `Asia Pacific (Mumbai) ap-south-1`.
6. Keep `Block all public access` enabled.
7. Click `Create bucket`.

Create SageMaker execution role:

```bash
cat > sagemaker-trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "sagemaker.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name $PROJECT-sagemaker-exec \
  --assume-role-policy-document file://sagemaker-trust.json

aws iam attach-role-policy \
  --role-name $PROJECT-sagemaker-exec \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

export SAGEMAKER_ROLE_ARN=$(aws iam get-role \
  --role-name $PROJECT-sagemaker-exec \
  --query Role.Arn \
  --output text)
```

Console steps for the same SageMaker role:

1. Open AWS Console.
2. Search `IAM`.
3. Go to `IAM` -> `Roles`.
4. Click `Create role`.
5. Trusted entity type: choose `AWS service`.
6. Service or use case: choose `SageMaker`.
7. Use case: choose `SageMaker - Execution`.
8. Click `Next`.
9. Permission policy: search and select `AmazonSageMakerFullAccess`.
10. Click `Next`.
11. Role name: enter `sagemaker-mlops-lab-sagemaker-exec`.
12. Click `Create role`.
13. Open the created role and copy the `ARN`.
14. Use that ARN as GitHub variable `SAGEMAKER_ROLE_ARN`.

Create MLflow EC2 in default VPC:

```bash
export AWS_REGION=ap-south-1
export PROJECT=sagemaker-mlops-lab
export KEY_PAIR_NAME=mlops-user
export MY_IP=$(curl -s https://checkip.amazonaws.com)/32

export VPC_ID=$(aws ec2 describe-vpcs \
  --region $AWS_REGION \
  --filters Name=isDefault,Values=true \
  --query "Vpcs[0].VpcId" \
  --output text)

export SUBNET_ID=$(aws ec2 describe-subnets \
  --region $AWS_REGION \
  --filters Name=vpc-id,Values=$VPC_ID \
  --query "Subnets[0].SubnetId" \
  --output text)

export SG_ID=$(aws ec2 describe-security-groups \
  --region $AWS_REGION \
  --filters Name=group-name,Values=$PROJECT-mlflow-sg Name=vpc-id,Values=$VPC_ID \
  --query "SecurityGroups[0].GroupId" \
  --output text)

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  export SG_ID=$(aws ec2 create-security-group \
    --region $AWS_REGION \
    --group-name $PROJECT-mlflow-sg \
    --description "MLflow tracking server" \
    --vpc-id $VPC_ID \
    --query GroupId \
    --output text)
fi

aws ec2 authorize-security-group-ingress --region $AWS_REGION --group-id $SG_ID --protocol tcp --port 22 --cidr $MY_IP || true
aws ec2 authorize-security-group-ingress --region $AWS_REGION --group-id $SG_ID --protocol tcp --port 5000 --cidr $MY_IP || true

cat > mlflow-user-data.sh <<'EOF'
#!/bin/bash
yum update -y
yum install -y python3-pip
python3 -m venv /opt/mlflow-venv
/opt/mlflow-venv/bin/pip install --upgrade pip
/opt/mlflow-venv/bin/pip install mlflow boto3
mkdir -p /opt/mlflow
nohup /opt/mlflow-venv/bin/mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:////opt/mlflow/mlflow.db --default-artifact-root /opt/mlflow/artifacts > /var/log/mlflow.log 2>&1 &
EOF

export AMI_ID=$(aws ec2 describe-images \
  --region $AWS_REGION \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-kernel-*-x86_64" "Name=state,Values=available" \
  --query "sort_by(Images, &CreationDate)[-1].ImageId" \
  --output text)

if [ "$AMI_ID" = "None" ] || [ -z "$AMI_ID" ]; then
  echo "No Amazon Linux 2023 AMI found in $AWS_REGION"
  exit 1
fi

export MLFLOW_INSTANCE_ID=$(aws ec2 run-instances \
  --region $AWS_REGION \
  --image-id $AMI_ID \
  --instance-type t3.micro \
  --key-name $KEY_PAIR_NAME \
  --subnet-id $SUBNET_ID \
  --security-group-ids $SG_ID \
  --user-data file://mlflow-user-data.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$PROJECT-mlflow}]" \
  --query "Instances[0].InstanceId" \
  --output text)

aws ec2 wait instance-running --region $AWS_REGION --instance-ids $MLFLOW_INSTANCE_ID

export MLFLOW_PUBLIC_IP=$(aws ec2 describe-instances \
  --region $AWS_REGION \
  --instance-ids $MLFLOW_INSTANCE_ID \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text)

export MLFLOW_TRACKING_URI=http://$MLFLOW_PUBLIC_IP:5000
echo $MLFLOW_TRACKING_URI
```

Windows PowerShell version:

```powershell
$env:AWS_REGION = "ap-south-1"
$env:PROJECT = "sagemaker-mlops-lab"
$env:KEY_PAIR_NAME = "mlops-user"
$env:ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
$env:MODEL_BUCKET = "$env:PROJECT-models-$env:ACCOUNT_ID"
$MY_IP = "$(Invoke-RestMethod https://checkip.amazonaws.com)/32"

$VPC_ID = aws ec2 describe-vpcs `
  --region $env:AWS_REGION `
  --filters Name=isDefault,Values=true `
  --query "Vpcs[0].VpcId" `
  --output text

$SUBNET_ID = aws ec2 describe-subnets `
  --region $env:AWS_REGION `
  --filters Name=vpc-id,Values=$VPC_ID `
  --query "Subnets[0].SubnetId" `
  --output text

$SG_ID = aws ec2 create-security-group `
  --region $env:AWS_REGION `
  --group-name "$env:PROJECT-mlflow-sg" `
  --description "MLflow tracking server" `
  --vpc-id $VPC_ID `
  --query GroupId `
  --output text

aws ec2 authorize-security-group-ingress --region $env:AWS_REGION --group-id $SG_ID --protocol tcp --port 22 --cidr $MY_IP
aws ec2 authorize-security-group-ingress --region $env:AWS_REGION --group-id $SG_ID --protocol tcp --port 5000 --cidr $MY_IP

@'
#!/bin/bash
yum update -y
yum install -y python3-pip
python3 -m venv /opt/mlflow-venv
/opt/mlflow-venv/bin/pip install --upgrade pip
/opt/mlflow-venv/bin/pip install mlflow boto3
mkdir -p /opt/mlflow
nohup /opt/mlflow-venv/bin/mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:////opt/mlflow/mlflow.db --default-artifact-root /opt/mlflow/artifacts > /var/log/mlflow.log 2>&1 &
'@ | Set-Content -Path mlflow-user-data.sh -Encoding ascii

$AMI_ID = aws ec2 describe-images `
  --region $env:AWS_REGION `
  --owners amazon `
  --filters "Name=name,Values=al2023-ami-2023.*-kernel-*-x86_64" "Name=state,Values=available" `
  --query "sort_by(Images, &CreationDate)[-1].ImageId" `
  --output text

if ($AMI_ID -eq "None" -or [string]::IsNullOrWhiteSpace($AMI_ID)) {
  throw "No Amazon Linux 2023 AMI found in $env:AWS_REGION"
}

$MLFLOW_INSTANCE_ID = aws ec2 run-instances `
  --region $env:AWS_REGION `
  --image-id $AMI_ID `
  --instance-type t3.micro `
  --key-name $env:KEY_PAIR_NAME `
  --subnet-id $SUBNET_ID `
  --security-group-ids $SG_ID `
  --user-data file://mlflow-user-data.sh `
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$env:PROJECT-mlflow}]" `
  --query "Instances[0].InstanceId" `
  --output text

aws ec2 wait instance-running --region $env:AWS_REGION --instance-ids $MLFLOW_INSTANCE_ID

$MLFLOW_PUBLIC_IP = aws ec2 describe-instances `
  --region $env:AWS_REGION `
  --instance-ids $MLFLOW_INSTANCE_ID `
  --query "Reservations[0].Instances[0].PublicIpAddress" `
  --output text

$env:MLFLOW_TRACKING_URI = "http://$MLFLOW_PUBLIC_IP`:5000"
$env:MLFLOW_TRACKING_URI
```

Console:

1. Search `EC2`.
2. Go to `EC2` -> `Security Groups`.
3. Click `Create security group`.
4. Name: `sagemaker-mlops-lab-mlflow-sg`.
5. VPC: choose the `default` VPC.
6. Add inbound rule: `Custom TCP`, port `5000`, source `My IP`.
7. Optional: add `SSH`, port `22`, source `My IP`.
8. Create the security group.
9. Go to `EC2` -> `Instances`.
10. Click `Launch instances`.
11. Name: `sagemaker-mlops-lab-mlflow`.
12. AMI: `Amazon Linux 2023`.
13. Instance type: `t3.micro`.
14. Key pair: choose existing key pair `mlops-user`.
15. Network: default VPC and public subnet.
16. Security group: select `sagemaker-mlops-lab-mlflow-sg`.
17. Advanced details -> User data: paste the MLflow install script from the CLI section.
18. Click `Launch instance`.
19. Copy the public IPv4 address.
20. Open `http://PUBLIC_IP:5000`.
21. Use this URL as `MLFLOW_TRACKING_URI`.

Create GitHub Actions OIDC role:

```bash
export GITHUB_REPO=end-to-end-sagemaker-mlops-pipeline-v2
export GITHUB_OIDC_PROVIDER_ARN=arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com

aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 || true

cat > github-actions-trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "$GITHUB_OIDC_PROVIDER_ARN"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:$GITHUB_OWNER/$GITHUB_REPO:*"
      }
    }
  }]
}
EOF

if aws iam get-role --role-name $PROJECT-github-actions >/dev/null 2>&1; then
  aws iam update-assume-role-policy \
    --role-name $PROJECT-github-actions \
    --policy-document file://github-actions-trust.json
else
  aws iam create-role \
    --role-name $PROJECT-github-actions \
    --assume-role-policy-document file://github-actions-trust.json
fi

cat > github-actions-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "sagemaker:*",
      "iam:PassRole",
      "s3:*",
      "logs:*",
      "cloudwatch:*"
    ],
    "Resource": "*"
  }]
}
EOF

aws iam put-role-policy \
  --role-name $PROJECT-github-actions \
  --policy-name $PROJECT-github-actions-policy \
  --policy-document file://github-actions-policy.json

export AWS_GITHUB_ACTIONS_ROLE_ARN=$(aws iam get-role \
  --role-name $PROJECT-github-actions \
  --query Role.Arn \
  --output text)

echo $AWS_GITHUB_ACTIONS_ROLE_ARN
```

Console:

1. AWS Console -> search `IAM`.
2. Go to `IAM` -> `Identity providers`.
3. Click `Add provider`.
4. Provider type: `OpenID Connect`.
5. Provider URL: `https://token.actions.githubusercontent.com`.
6. Audience: `sts.amazonaws.com`.
7. Click `Add provider`.
8. Go to `IAM` -> `Roles`.
9. Click `Create role`.
10. Trusted entity: choose `Web identity`.
11. Identity provider: `token.actions.githubusercontent.com`.
12. Audience: `sts.amazonaws.com`.
13. Create role name: `sagemaker-mlops-lab-github-actions`.
14. Open the role -> `Trust relationships` -> `Edit trust policy`.
15. Add repo condition: `repo:YOUR_GITHUB_OWNER/YOUR_GITHUB_REPO:*`.
16. Open `Permissions` -> `Add permissions` -> `Create inline policy`.
17. Use JSON policy allowing SageMaker, S3, CloudWatch Logs, and `iam:PassRole`.
18. Copy the role ARN.
19. GitHub repo -> `Settings` -> `Secrets and variables` -> `Actions`.
20. Add secret `AWS_GITHUB_ACTIONS_ROLE_ARN`.
21. Add variables `SAGEMAKER_ROLE_ARN`, `MODEL_BUCKET`, and `MLFLOW_TRACKING_URI`.

Create Lambda and API Gateway after the model artifact exists:

```bash
python -c "import zipfile; zipfile.ZipFile('lambda.zip','w').write('lambda/inference_app.py','inference_app.py')"

aws lambda create-function \
  --function-name $PROJECT-inference \
  --runtime python3.11 \
  --role YOUR_LAMBDA_ROLE_ARN \
  --handler inference_app.handler \
  --zip-file fileb://lambda.zip \
  --timeout 30 \
  --environment "Variables={MODEL_BUCKET=$MODEL_BUCKET,MODEL_KEY=artifacts/YOUR_MODEL_KEY/model.tar.gz}"
```

Console for Lambda role:

1. AWS Console -> search `IAM`.
2. Go to `IAM` -> `Roles`.
3. Click `Create role`.
4. Trusted entity: `AWS service`.
5. Service: `Lambda`.
6. Attach `AWSLambdaBasicExecutionRole`.
7. Role name: `sagemaker-mlops-lab-lambda`.
8. Open role -> `Permissions` -> `Create inline policy`.
9. Add `s3:GetObject` permission for `arn:aws:s3:::YOUR_MODEL_BUCKET/*`.
10. Copy the Lambda role ARN.

Console for Lambda function:

1. Create `lambda.zip` using the CLI zip command above.
2. AWS Console -> search `Lambda`.
3. Go to `Lambda` -> `Functions`.
4. Click `Create function`.
5. Choose `Author from scratch`.
6. Function name: `sagemaker-mlops-lab-inference`.
7. Runtime: `Python 3.11`.
8. Permissions: select existing role `sagemaker-mlops-lab-lambda`.
9. Create function.
10. `Code` -> `Upload from` -> `.zip file` -> upload `lambda.zip`.
11. `Configuration` -> `Environment variables`.
12. Add `MODEL_BUCKET`.
13. Add `MODEL_KEY` after training, using the real S3 `model.tar.gz` key.
14. `Configuration` -> `General configuration` -> set timeout to `30 seconds`.

Console for API Gateway:

1. AWS Console -> search `API Gateway`.
2. Go to `API Gateway` -> `APIs`.
3. Click `Create API`.
4. Under `HTTP API`, click `Build`.
5. Integration: choose `Lambda`.
6. Lambda function: `sagemaker-mlops-lab-inference`.
7. API name: `sagemaker-mlops-lab-api`.
8. Route method: `POST`.
9. Route path: `/predict`.
10. Stage: `$default`.
11. Enable auto deploy.
12. Create API.
13. Copy the Invoke URL and use it as `API_URL`.

## GitHub Actions Setup

Add this repository secret:

- `AWS_GITHUB_ACTIONS_ROLE_ARN`

Add these repository variables:

- `SAGEMAKER_ROLE_ARN`
- `MODEL_BUCKET`
- `MLFLOW_TRACKING_URI`, for example `http://EC2_PUBLIC_IP:5000`

When you push to `main`, GitHub Actions validates the lab, assumes the AWS role by OIDC, creates or updates the SageMaker pipeline, and starts training.

Print values to add in GitHub:

```bash
echo "AWS_GITHUB_ACTIONS_ROLE_ARN=$AWS_GITHUB_ACTIONS_ROLE_ARN"
echo "SAGEMAKER_ROLE_ARN=$SAGEMAKER_ROLE_ARN"
echo "MODEL_BUCKET=$MODEL_BUCKET"
echo "MLFLOW_TRACKING_URI=$MLFLOW_TRACKING_URI"
```

Add them using GitHub CLI:

```bash
export GITHUB_OWNER=YOUR_GITHUB_USERNAME_OR_ORG
export GITHUB_REPO=end-to-end-sagemaker-mlops-pipeline-v2

gh secret set AWS_GITHUB_ACTIONS_ROLE_ARN \
  --repo $GITHUB_OWNER/$GITHUB_REPO \
  --body "$AWS_GITHUB_ACTIONS_ROLE_ARN"

gh variable set SAGEMAKER_ROLE_ARN \
  --repo $GITHUB_OWNER/$GITHUB_REPO \
  --body "$SAGEMAKER_ROLE_ARN"

gh variable set MODEL_BUCKET \
  --repo $GITHUB_OWNER/$GITHUB_REPO \
  --body "$MODEL_BUCKET"

gh variable set MLFLOW_TRACKING_URI \
  --repo $GITHUB_OWNER/$GITHUB_REPO \
  --body "$MLFLOW_TRACKING_URI"
```

Manual GitHub navigation:

1. GitHub repo -> `Settings`.
2. Go to `Secrets and variables` -> `Actions`.
3. Open `Secrets` -> add `AWS_GITHUB_ACTIONS_ROLE_ARN`.
4. Open `Variables` -> add `SAGEMAKER_ROLE_ARN`, `MODEL_BUCKET`, and `MLFLOW_TRACKING_URI`.

Console:

1. GitHub repo -> `Actions`.
2. Open workflow `SageMaker MLOps Lab`.
3. Click `Run workflow`.
4. Keep `start_pipeline` enabled.
5. Click `Run workflow`.
6. Open the running workflow.
7. Watch `validate`.
8. Watch `run-pipeline`.
9. AWS Console -> search `SageMaker`.
10. Go to `SageMaker` -> `Pipelines`.
11. Open `sagemaker-mlops-lab`.
12. Open latest execution.
13. Go to `SageMaker` -> `Training jobs`.
14. Open the latest training job.
15. Go to `SageMaker` -> `Model registry`.
16. Open `sagemaker-mlops-lab-models`.
17. EC2 -> open MLflow URL `http://PUBLIC_IP:5000`.
18. Open experiment `hyderabad-house-price-lab`.
19. S3 -> open model bucket.
20. Find latest `model.tar.gz` under `artifacts`.
21. Copy the object key for Lambda `MODEL_KEY`.

## Demo Payload

After training, update Lambda with the model artifact key from S3:

For this completed lab run, the model artifact is:

```text
s3://sagemaker-mlops-lab-models-559352513391/artifacts/pipelines-qvytpjni9df7-TrainHyderabadHouseP-kMMtoaGI99/output/model.tar.gz
```

Set the Lambda model variables:

```bash
export MODEL_BUCKET=sagemaker-mlops-lab-models-559352513391
export MODEL_KEY=artifacts/pipelines-qvytpjni9df7-TrainHyderabadHouseP-kMMtoaGI99/output/model.tar.gz
```

Update Lambda:

```bash
aws lambda update-function-configuration \
  --region ap-south-1 \
  --function-name sagemaker-mlops-lab-inference \
  --environment "Variables={MODEL_BUCKET=$MODEL_BUCKET,MODEL_KEY=$MODEL_KEY}"
```

Post-training checks:

1. Open MLflow and check experiment `hyderabad-house-price-lab`.
2. Open SageMaker -> `Model registry` -> check package group `sagemaker-mlops-lab-models`.
3. Open Lambda -> `sagemaker-mlops-lab-inference` -> confirm env vars `MODEL_BUCKET` and `MODEL_KEY`.
4. Open API Gateway -> confirm route `POST /predict`.

Console:

1. AWS Console -> search `Lambda`.
2. Open `Lambda` -> `Functions`.
3. Open `sagemaker-mlops-lab-inference`.
4. Go to `Configuration` -> `Environment variables`.
5. Edit `MODEL_BUCKET` if needed.
6. Set `MODEL_KEY` to the copied S3 key for `model.tar.gz`.
7. Click `Save`.

Test API Gateway:

```bash
export API_URL=https://zxbyhhvixj.execute-api.ap-south-1.amazonaws.com

curl -X POST "$API_URL/predict" \
  -H "content-type: application/json" \
  -d '{"features":[1200,3,2,5,8]}'
```

Expected response:

```json
{
  "problem": "Hyderabad house price prediction",
  "estimated_price_lakhs": 40.55,
  "estimated_price_inr": 4054907.26
}
```

Console:

1. AWS Console -> search `API Gateway`.
2. Open `API Gateway` -> `APIs`.
3. Open `sagemaker-mlops-lab-api`.
4. Copy the `Invoke URL`.
5. Use that URL in curl as `API_URL`.
6. You can also use Postman with method `POST`, path `/predict`, and JSON body `{"features":[1200,3,2,5,8]}`.

Run frontend locally:

```bash
cd frontend
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

Do not open `index.html` directly from disk because browser origin becomes `null` and API Gateway CORS can block it.

Console frontend hosting:

1. AWS Console -> search `S3`.
2. Open the frontend bucket.
3. Upload `frontend/index.html`.
4. Go to `Properties`.
5. Open `Static website hosting`.
6. Click `Edit`.
7. Enable website hosting.
8. Index document: `index.html`.
9. Save changes.
10. Go to `Permissions`.
11. For a public classroom demo, allow public read only on this frontend bucket.
12. Copy the S3 website endpoint and open it in the browser.

## Cleanup In Console

One-command cleanup from Bash:

```bash
bash scripts/delete_lab.sh
```

To also delete the account-level GitHub OIDC provider, run:

```bash
DELETE_GITHUB_OIDC_PROVIDER=true bash scripts/delete_lab.sh
```

Keep `DELETE_GITHUB_OIDC_PROVIDER=false` if the same AWS account uses GitHub Actions OIDC for other repos.

1. SageMaker -> `Pipelines` -> delete `sagemaker-mlops-lab`.
2. SageMaker -> `Model registry` -> delete model packages and package group.
3. Lambda -> `Functions` -> delete `sagemaker-mlops-lab-inference`.
4. API Gateway -> `APIs` -> delete `sagemaker-mlops-lab-api`.
5. EC2 -> `Instances` -> terminate `sagemaker-mlops-lab-mlflow`.
6. EC2 -> `Security Groups` -> delete `sagemaker-mlops-lab-mlflow-sg`.
7. S3 -> empty and delete model/frontend buckets.
8. IAM -> `Roles` -> delete SageMaker, GitHub Actions, and Lambda lab roles.
9. IAM -> `Identity providers` -> delete GitHub OIDC provider only if it is not used by other repos.
retry oidc
