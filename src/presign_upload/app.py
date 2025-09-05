import os
import json
import uuid
import boto3
from botocore.config import Config
from datetime import datetime
from typing import Dict, List

# ---------------------------------------------------------------------------
# 1. Setup AWS clients
# ---------------------------------------------------------------------------
REGION = os.environ.get("AWS_REGION", "ap-south-1")

# Force SigV4 + regional endpoint for presigned URLs
s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4"),
)

# DynamoDB resource for saving file metadata
dynamodb = boto3.resource("dynamodb")

# ---------------------------------------------------------------------------
# 2. Environment variables from template.yaml
# ---------------------------------------------------------------------------
BUCKET = os.environ["BUCKET_NAME"]                # S3 bucket name
TTL = int(os.environ.get("PRESIGN_TTL_SECONDS", "900"))  # URL expiry (seconds)
FILES_TABLE = os.environ["FILES_TABLE_NAME"]      # DynamoDB table name

files_table = dynamodb.Table(FILES_TABLE)

# ---------------------------------------------------------------------------
# 3. Helper: consistent API Gateway response format
# ---------------------------------------------------------------------------
def _resp(status: int, body: dict):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # Allow all (for frontend CORS)
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        },
        "body": json.dumps(body),
    }

# ---------------------------------------------------------------------------
# 4. Helper: extract Cognito info from API Gateway event (authorizer claims)
# ---------------------------------------------------------------------------
def _get_cognito_info_from_event(event: dict) -> Dict[str, object]:
    """
    Safely extract user info from event.requestContext.authorizer.claims.

    Returns:
      {
        "username": <cognito username or sub>,
        "email": <email if present>,
        "groups": [<group1>, <group2>, ...]  # empty list if none
      }
    """
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {}) or {}
    # username: prefer email-like claim if present; fall back to cognito:username or sub
    username = claims.get("email") or claims.get("cognito:username") or claims.get("sub") or "unknown-user"
    email = claims.get("email")

    groups_raw = claims.get("cognito:groups") or claims.get("groups") or ""
    groups: List[str] = []
    if isinstance(groups_raw, list):
        groups = groups_raw
    elif isinstance(groups_raw, str) and groups_raw:
        # Cognito often provides a single string for groups; split on comma if needed
        # Trim whitespace and ignore empty tokens
        groups = [g.strip() for g in groups_raw.split(",") if g.strip()]

    return {"username": username, "email": email, "groups": groups}

# ---------------------------------------------------------------------------
# 5. RBAC helper
# ---------------------------------------------------------------------------
def _has_any_group(user_groups: List[str], allowed: List[str]) -> bool:
    if not user_groups:
        return False
    user_set = set([g.lower() for g in user_groups])
    allowed_set = set([g.lower() for g in allowed])
    return len(user_set.intersection(allowed_set)) > 0

# ---------------------------------------------------------------------------
# 6. Lambda handler: generates presigned URL + logs metadata in DynamoDB
#    RBAC: only 'uploader' or 'admin' allowed to create presigned upload URLs
# ---------------------------------------------------------------------------
def handler(event, context):
    try:
        # ---- Cognito info + RBAC ----
        cognito = _get_cognito_info_from_event(event)
        user_email = cognito.get("email") or cognito.get("username") or "unknown-user"
        user_groups = cognito.get("groups", [])

        # If no authorizer claims present, return 401 (not authenticated)
        if cognito.get("username") == "unknown-user" and not user_email and not user_groups:
            return _resp(401, {"error": "unauthenticated - missing Cognito claims"})

        # Allowed groups for upload
        allowed_groups = ["admin", "uploader"]
        if not _has_any_group(user_groups, allowed_groups):
            # 403: Forbidden - authenticated but not authorized
            return _resp(403, {"error": "forbidden - requires uploader or admin group"})

        # ---- Parse request body ----
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body or "{}")

        filename = body.get("filename")
        if not filename:
            return _resp(400, {"error": "filename is required"})

        # ---- Generate unique file ID + S3 object key ----
        file_id = str(uuid.uuid4())
        key = f"uploads/{file_id}/{filename}"

        # ---- Generate presigned PUT URL ----
        url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=TTL,
        )

        # ---- Save metadata into DynamoDB ----
        files_table.put_item(
            Item={
                "fileId": file_id,                    # UUID for file
                "s3Key": key,                         # Path inside S3
                "filename": filename,                 # Original filename
                "uploadedAt": datetime.utcnow().isoformat(),  # Upload timestamp
                "uploadedBy": user_email,             # From Cognito claims
            }
        )

        # ---- Return presigned URL + metadata ----
        return _resp(
            200,
            {
                "fileId": file_id,
                "key": key,
                "url": url,
                "expiresIn": TTL,
                "uploadedBy": user_email,
            },
        )

    except Exception as e:
        # Keep error payload JSON (avoid API Gateway 502s)
        print("❌ Error in presign_upload:", str(e))
        return _resp(500, {"error": str(e)})
