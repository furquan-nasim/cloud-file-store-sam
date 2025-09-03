import os
import json
import uuid
import boto3
from botocore.config import Config
from datetime import datetime

# ---------------------------------------------------------------------------
# 1. Setup AWS clients
# ---------------------------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "ap-south-1")

# ✅ Force SigV4 + regional endpoint for presigned URLs
s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4"),
)

# ✅ DynamoDB client for saving file metadata
dynamodb = boto3.resource("dynamodb")

# ---------------------------------------------------------------------------
# 2. Environment variables from template.yaml
# ---------------------------------------------------------------------------
BUCKET = os.environ["BUCKET_NAME"]              # S3 bucket name
TTL = int(os.environ.get("PRESIGN_TTL_SECONDS", "900"))  # URL expiry (seconds)
FILES_TABLE = os.environ["FILES_TABLE_NAME"]    # DynamoDB table name for file metadata

files_table = dynamodb.Table(FILES_TABLE)

# ---------------------------------------------------------------------------
# 3. Helper: format consistent API Gateway responses
# ---------------------------------------------------------------------------
def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # CORS allow all
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        },
        "body": json.dumps(body),
    }

# ---------------------------------------------------------------------------
# 4. Lambda handler: generates presigned URL + logs metadata in DynamoDB
# ---------------------------------------------------------------------------
def handler(event, context):
    try:
        # 🔹 Parse request body
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body or "{}")

        filename = body.get("filename")
        if not filename:
            return _resp(400, {"error": "filename is required"})

        # 🔹 Generate unique file ID + S3 object key
        file_id = str(uuid.uuid4())
        key = f"uploads/{file_id}/{filename}"

        # 🔹 Generate presigned PUT URL (valid for TTL seconds)
        url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=TTL,
        )

        # 🔹 Save metadata into DynamoDB (for listing later)
        files_table.put_item(
            Item={
                "fileId": file_id,             # UUID for file
                "s3Key": key,                  # Path inside S3
                "filename": filename,          # Original file name
                "uploadedAt": datetime.utcnow().isoformat(),  # Upload timestamp
            }
        )

        # 🔹 Return presigned URL + metadata
        return _resp(
            200,
            {
                "fileId": file_id,
                "key": key,
                "url": url,
                "expiresIn": TTL,
            },
        )

    except Exception as e:
        print("Error in presign_upload:", str(e))
        return _resp(500, {"error": str(e)})
