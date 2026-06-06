import json
import boto3
import os

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket = os.environ['MODEL_BUCKET']

    response = s3.list_objects_v2(Bucket=bucket)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Lambda is working",
            "bucket": bucket,
            "objects": response.get("Contents", [])
        })
    }
