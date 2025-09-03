import json
import os
import uuid
import time
import boto3

# ✅ DynamoDB resource
dynamodb = boto3.resource("dynamodb")
history_table = dynamodb.Table(os.environ["HISTORY_TABLE_NAME"])

def handler(event, context):
    """
    Lambda handler for POST /files/record-download
    Records a new download event in DynamoDB
    """

    try:
        # 1️⃣ Parse request body
        body = json.loads(event.get("body", "{}"))
        file_id = body.get("fileId")
        user_id = event["requestContext"]["authorizer"]["claims"]["sub"]

        if not file_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "fileId is required"})
            }

        # 2️⃣ Create a record
        download_record = {
            "downloadId": str(uuid.uuid4()),
            "fileId": file_id,
            "userId": user_id,
            "timestamp": int(time.time())
        }

        # 3️⃣ Save to DynamoDB
        history_table.put_item(Item=download_record)

        # 4️⃣ Return success
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(download_record)
        }

    except Exception as e:
        print("Error recording download:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
