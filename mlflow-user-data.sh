#!/bin/bash
yum update -y
yum install -y python3-pip
python3 -m venv /opt/mlflow-venv
/opt/mlflow-venv/bin/pip install --upgrade pip
/opt/mlflow-venv/bin/pip install mlflow boto3
mkdir -p /opt/mlflow
nohup /opt/mlflow-venv/bin/mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri sqlite:////opt/mlflow/mlflow.db \
  --default-artifact-root /opt/mlflow/artifacts \
  > /var/log/mlflow.log 2>&1 &
