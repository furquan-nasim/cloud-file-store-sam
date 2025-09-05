# src/record_download/app.py
"""
Record download audit events into the DownloadHistoryTable.

Expected input (JSON body):
  {
    "s3Key": "uploads/....",
    "versionId": "<optional>",
    "downloadName": "<optional>",
    "asAttachment": true|false
  }

Environment variables required:
  - HISTORY_TABLE_NAME   (DynamoDB table for download history)
  - PRESIGN_TTL_SECONDS  (optional, to record TTL used)
"""

import os
import json
import uuid
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

# ------------------------------
# Configuration / clients
# ------------------------------
REGION = os.environ.get("AWS_REGION", "ap-south-1")
HISTORY_TABLE_NAME = os.environ.get("HISTORY_TABLE_NAME")
TTL = int(os.environ.get("PRESIGN_TTL_SECONDS", "900"))

dynamodb = boto3.resource("dynamodb", region_name=REGION)
history_table = dynamodb.Table(HISTORY_TABLE_NAME)

# Allowed groups for writing download records (adjust as desired)
ALLOWED_GROUPS = {"viewer", "uploader", "admin"}


# ------------------------------
# Helpers
# ------------------------------
def _resp(status: int, body: dict):
    """Uniform JSON + CORS response."""
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


def _get_cognito_info_from_event(event):
    """
    Extract identity information from API Gateway authorizer.
    Returns a dict containing:
      - username
      - email
      - sub
      - groups  (list)
      - is_admin (bool)  <-- convenience flag if 'admin' present
    Works with both older 'authorizer.claims' and newer 'authorizer.jwt.claims'.
    """
    try:
        auth = event.get("requestContext", {}).get("authorizer", {}) or {}
        claims = {}

        # Newer API Gateway -> authorizer.jwt.claims
        jwt = auth.get("jwt")
        if jwt and isinstance(jwt, dict):
            claims = jwt.get("claims", {}) or {}

        # Older shape -> authorizer.claims
        if not claims:
            claims = auth.get("claims", {}) or {}

        # Groups may be in custom:groups, or "cognito:groups" (space/comma separated)
        raw_groups = claims.get("cognito:groups") or claims.get("groups") or claims.get("custom:groups") or ""
        groups = []
        if isinstance(raw_groups, str) and raw_groups:
            # AWS often returns a space-separated string for cognito:groups
            # some setups may store a JSON list; handle both.
            raw = raw_groups.strip()
            if raw.startswith("[") and raw.endswith("]"):
                # try parse as JSON list
                try:
                    groups = json.loads(raw)
                except Exception:
                    # fallback to whitespace split
                    groups = raw.strip("[]").replace('"', "").split()
            else:
                # split by whitespace or comma
                if "," in raw:
                    groups = [g.strip() for g in raw.split(",") if g.strip()]
                else:
                    groups = [g.strip() for g in raw.split() if g.strip()]

        username = claims.get("cognito:username") or claims.get("username") or claims.get("email") or claims.get("sub")
        email = claims.get("email")
        sub = claims.get("sub")

        is_admin = "admin" in [g.lower() for g in groups]

        return {
            "username": username,
            "email": email,
            "sub": sub,
            "groups": groups,
            "is_admin": is_admin,
        }
    except Exception:
        return {"username": None, "email": None, "sub": None, "groups": [], "is_admin": False}


# ------------------------------
# Lambda handler
# ------------------------------
def handler(event, context):
    """
    Accepts a POST request with JSON body describing the download.
    Performs RBAC (only allowed groups can write download records),
    writes an item to DownloadHistoryTable and returns the created record id.
    """
    try:
        # 1) Auth info & RBAC
        identity = _get_cognito_info_from_event(event)
        user_email = identity.get("email") or identity.get("username") or "anonymous"
        groups = [g.lower() for g in (identity.get("groups") or [])]

        if not set(groups) & ALLOWED_GROUPS:
            # Not in any allowed group
            return _resp(403, {"error": "forbidden", "reason": "user not in allowed groups"})

        # 2) Parse body
        body = event.get("body", "{}")
        if isinstance(body, str):
            try:
                body = json.loads(body or "{}")
            except Exception:
                return _resp(400, {"error": "invalid JSON body"})

        s3_key = body.get("s3Key") or body.get("key") or body.get("fileKey")
        if not s3_key:
            return _resp(400, {"error": "s3Key (or key) is required in body"})

        version_id = body.get("versionId") or ""
        download_name = body.get("downloadName") or ""
        as_attachment = bool(body.get("asAttachment", True))

        # 3) Create history record
        download_id = str(uuid.uuid4())
        item = {
            "downloadId": download_id,
            "s3Key": s3_key,
            "versionId": version_id or "",
            "requestedBy": user_email,
            "requestedAt": datetime.utcnow().isoformat(),
            "asAttachment": bool(as_attachment),
            "downloadName": download_name or "",
            "ttlSeconds": TTL,
            # optional: store groups snapshot for auditing
            "requesterGroups": groups,
        }

        # Best-effort write; if write fails return 500
        history_table.put_item(Item=item)

        return _resp(201, {"recordCreated": True, "downloadId": download_id, "s3Key": s3_key})

    except ClientError as ce:
        # DynamoDB / AWS client error
        return _resp(500, {"error": "AWS error", "details": str(ce)})
    except Exception as e:
        # Catch-all
        return _resp(500, {"error": f"{type(e).__name__}: {str(e)}"})
