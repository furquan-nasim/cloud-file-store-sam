import json
import os
import boto3
from boto3.dynamodb.conditions import Key

# ✅ Initialize DynamoDB resource once (reused across Lambda invocations)
dynamodb = boto3.resource("dynamodb")

# ✅ Get table name from environment variable (set in template.yaml)
files_table = dynamodb.Table(os.environ["FILES_TABLE_NAME"])

def handler(event, context):
    """
    Lambda handler for GET /files/list
    This function reads all file metadata from the DynamoDB table
    and returns it as a JSON array.
    """

    try:
        # 1️⃣ Query the DynamoDB table
        # For now we scan the whole table (not filtered per user)
        response = files_table.scan()

        # 2️⃣ Extract items from response (list of file records)
        items = response.get("Items", [])

        # 3️⃣ Convert DynamoDB records into a cleaner list of dicts
        files = [
            {
                "fileId": item.get("fileId"),       # Unique file ID (UUID)
                "key": item.get("s3Key"),          # Path in S3 bucket
                "uploadedAt": item.get("uploadedAt")  # Upload timestamp
            }
            for item in items
        ]

        # 4️⃣ Return HTTP 200 + JSON body
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"  # CORS: allow frontend
            },
            "body": json.dumps(files)
        }

    except Exception as e:
        # 5️⃣ If anything goes wrong, return HTTP 500 with error message
        print("Error listing files:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
