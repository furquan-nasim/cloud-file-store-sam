# src/presign_download/app.py
"""
Generate a presigned *download* (GET) URL for an S3 object and
write an audit record to DynamoDB (DownloadHistoryTable).

Query params:
  - key (required): S3 object key
  - versionId (optional): specific object version (for versioned buckets)
  - downloadName (optional): suggest a filename to the browser
  - asAttachment (optional): "true" (default) to trigger save dialog, "false" to open inline

Environment:
  - BUCKET_NAME
  - PRESIGN_TTL_SECONDS (default 900)
  - CHECK_EXISTS ("true"/"false"; default "true")
  - HISTORY_TABLE_NAME  <-- required for audit logging
"""

import os
import json
import uuid
import urllib.parse
from datetime import datetime
from typing import Dict, List, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# ----------------------------
# Configuration / Clients
# ----------------------------
REGION = os.environ.get("AWS_REGION", "ap-south-1")

s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4"),
)

dynamodb = boto3.resource("dynamodb")

BUCKET = os.environ["BUCKET_NAME"]
TTL = int(os.environ.get("PRESIGN_TTL_SECONDS", "900"))
CHECK_EXISTS = os.environ.get("CHECK_EXISTS", "true").lower() == "true"
HISTORY_TABLE_NAME = os.environ["HISTORY_TABLE_NAME"]
history_table = dynamodb.Table(HISTORY_TABLE_NAME)


def _resp(status: int, body: dict) -> dict:
    """Consistent JSON + CORS response."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        },
        "body": json.dumps(body),
    }


# ----------------------------
# Shared Cognito helper + RBAC
# ----------------------------
def _get_cognito_info_from_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely extract user info from event.requestContext.authorizer.claims
    Returns a dict: { "username": str, "email": Optional[str], "groups": List[str] }
    """
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {}) or {}
    # Prefer email, then cognito:username, then sub
    username = claims.get("email") or claims.get("cognito:username") or claims.get("sub") or "unknown-user"
    email = claims.get("email")
    groups_raw = claims.get("cognito:groups") or claims.get("groups") or ""
    groups: List[str] = []
    if isinstance(groups_raw, list):
        groups = groups_raw
    elif isinstance(groups_raw, str) and groups_raw:
        groups = [g.strip() for g in groups_raw.split(",") if g.strip()]
    return {"username": username, "email": email, "groups": groups}


def _has_any_group(user_groups: List[str], allowed: List[str]) -> bool:
    if not user_groups:
        return False
    user_set = set(g.lower() for g in user_groups)
    allowed_set = set(g.lower() for g in allowed)
    return len(user_set.intersection(allowed_set)) > 0


def _get_ip_and_ua(event: Dict[str, Any]):
    """Extract client IP and User-Agent from headers if available."""
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    ip = headers.get("x-forwarded-for", "")
    ip = ip.split(",")[0].strip() if ip else ""
    ua = headers.get("user-agent", "")
    return ip, ua


def handler(event, context):
    """
    Handler for GET /files/presign-download
    Steps:
      1) Authenticate + RBAC (viewer/uploader/admin)
      2) Read/normalize query params.
      3) (Optional) HEAD-check the object so we can return 404 if missing.
      4) Generate a presigned GET URL (optionally set response headers).
      5) Write an audit record to DynamoDB (best-effort).
    """
    try:
        # --- 1) Auth + RBAC ---
        cognito = _get_cognito_info_from_event(event)
        username = cognito.get("username")
        email = cognito.get("email")
        groups = cognito.get("groups", [])

        # If no meaningful identity present, treat as unauthenticated
        if username == "unknown-user" and not email and not groups:
            return _resp(401, {"error": "unauthenticated - missing Cognito claims"})

        allowed_groups = ["admin", "uploader", "viewer"]
        if not _has_any_group(groups, allowed_groups):
            return _resp(403, {"error": "forbidden - requires viewer/uploader/admin group"})

        # --- 2) Read & normalize query params ---
        params = event.get("queryStringParameters") or {}
        if isinstance(params, str):
            # rare case: URL-encoded string
            params = dict(urllib.parse.parse_qsl(params))

        raw_key = params.get("key")
        if not raw_key:
            return _resp(400, {"error": "query parameter 'key' is required"})

        key = urllib.parse.unquote(raw_key)  # API Gateway often encodes slashes %2F
        version_id = params.get("versionId") or None
        as_attachment = (params.get("asAttachment", "true").lower() == "true")
        download_name = params.get("downloadName") or None

        presign_params = {"Bucket": BUCKET, "Key": key}
        if version_id:
            presign_params["VersionId"] = version_id

        if download_name:
            disposition_type = "attachment" if as_attachment else "inline"
            content_disp = f'{disposition_type}; filename="{download_name}"'
            presign_params["ResponseContentDisposition"] = content_disp

        # --- 3) Optional existence check (HEAD) ---
        if CHECK_EXISTS:
            try:
                head_kwargs = {"Bucket": BUCKET, "Key": key}
                if version_id:
                    head_kwargs["VersionId"] = version_id
                s3.head_object(**head_kwargs)
            except ClientError as ce:
                code = ce.response.get("Error", {}).get("Code")
                if code in ("404", "NoSuchKey", "NotFound"):
                    return _resp(404, {"error": "object not found", "key": key})
                raise

        # --- 4) Generate presigned GET URL ---
        url = s3.generate_presigned_url(
            "get_object",
            Params=presign_params,
            ExpiresIn=TTL,
        )

        # --- 5) Audit log to DynamoDB (best-effort) ---
        download_id = str(uuid.uuid4())
        requested_by = email or username or "unknown"
        ip, ua = _get_ip_and_ua(event)

        history_item = {
            "downloadId": download_id,
            "s3Key": key,
            "versionId": version_id or "",
            "requestedBy": requested_by,
            "requestedAt": datetime.utcnow().isoformat(),
            "ip": ip,
            "userAgent": ua,
            "asAttachment": as_attachment,
            "downloadName": download_name or "",
            "ttlSeconds": TTL,
            "userGroups": groups,
        }

        try:
            history_table.put_item(Item=history_item)
        except Exception as log_err:
            # Don't fail the request if logging fails; print to CloudWatch for diagnosis
            print("WARN: failed to write download history:", str(log_err))

        return _resp(200, {"url": url, "expiresIn": TTL})

    except Exception as e:
        # Ensure we *always* return JSON (avoid API 502 from unhandled exceptions)
        return _resp(500, {"error": f"{type(e).__name__}: {str(e)}"})
