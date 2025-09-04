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


def _resp(status: int, body: dict):
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


def _get_requester(event) -> str:
    """
    Try to pull a human-friendly identity from the Cognito JWT.
    Falls back to 'anonymous' if not found.
    """
    try:
        claims = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("jwt", {})
            .get("claims", {})
        )
        # Prefer email if present; else cognito:username; else sub
        return claims.get("email") or claims.get("cognito:username") or claims.get("sub") or "anonymous"
    except Exception:
        return "anonymous"


def _get_ip_and_ua(event):
    """Extract client IP and User-Agent from headers if available."""
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    ip = headers.get("x-forwarded-for", "")
    # x-forwarded-for can be a list "client, proxy1, proxy2"
    ip = ip.split(",")[0].strip() if ip else ""
    ua = headers.get("user-agent", "")
    return ip, ua


def handler(event, context):
    """
    Handler for GET /files/presign-download
    Steps:
      1) Read/normalize query params.
      2) (Optional) HEAD-check the object so we can return 404 if missing.
      3) Generate a presigned GET URL (optionally set response headers).
      4) Write an audit record to DynamoDB.
    """
    try:
        # --- 1) Read & normalize query params ---
        params = event.get("queryStringParameters") or {}
        if isinstance(params, str):
            # rare case: URL-encoded string
            params = dict(urllib.parse.parse_qsl(params))

        raw_key = params.get("key")
        if not raw_key:
            return _resp(400, {"error": "query parameter 'key' is required"})

        key = urllib.parse.unquote(raw_key)  # API Gateway often encodes slashes %2F

        # Optional
        version_id = params.get("versionId") or None
        as_attachment = (params.get("asAttachment", "true").lower() == "true")
        download_name = params.get("downloadName") or None

        presign_params = {"Bucket": BUCKET, "Key": key}
        if version_id:
            presign_params["VersionId"] = version_id

        # Optional content-disposition for nicer download behavior
        if download_name:
            disposition_type = "attachment" if as_attachment else "inline"
            content_disp = f'{disposition_type}; filename="{download_name}"'
            presign_params["ResponseContentDisposition"] = content_disp

        # --- 2) Optional existence check (HEAD) ---
        if CHECK_EXISTS:
            try:
                head_kwargs = {"Bucket": BUCKET, "Key": key}
                if version_id:
                    head_kwargs["VersionId"] = version_id
                s3.head_object(**head_kwargs)  # raises if missing
            except ClientError as ce:
                code = ce.response.get("Error", {}).get("Code")
                if code in ("404", "NoSuchKey", "NotFound"):
                    return _resp(404, {"error": "object not found", "key": key})
                # other S3 errors bubble up
                raise

        # --- 3) Generate presigned GET URL ---
        url = s3.generate_presigned_url(
            "get_object",
            Params=presign_params,
            ExpiresIn=TTL,
        )

        # --- 4) Audit log to DynamoDB ---
        download_id = str(uuid.uuid4())
        requested_by = _get_requester(event)
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
        }
        # Best-effort logging; don't fail the request if logging fails
        try:
            history_table.put_item(Item=history_item)
        except Exception as log_err:
            # Still return URL; print for CW logs
            print("WARN: failed to write download history:", str(log_err))

        return _resp(200, {"url": url, "expiresIn": TTL})

    except Exception as e:
        # Ensure we *always* return JSON (avoid API 502 from unhandled exceptions)
        return _resp(500, {"error": f"{type(e).__name__}: {str(e)}"})
