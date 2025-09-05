# src/list_files/app.py
"""
Lambda: List all files (GET /files/list)

- Reads file metadata from DynamoDB (FILES_TABLE_NAME).
- Only authenticated users in allowed groups can access.
- Returns JSON array of files.
"""

import os
import json
import boto3
from typing import Dict, List, Any

# ----------------------------
# AWS clients
# ----------------------------
dynamodb = boto3.resource("dynamodb")
files_table = dynamodb.Table(os.environ["FILES_TABLE_NAME"])

# ----------------------------
# Helpers
# ----------------------------
def _resp(status: int, body: dict) -> dict:
    """Consistent API Gateway JSON + CORS response."""
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


def _get_cognito_info_from_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract Cognito claims from request.
    Returns { username, email, groups }
    """
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {}) or {}
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
    """Check if user belongs to any allowed group."""
    if not user_groups:
        return False
    user_set = set(g.lower() for g in user_groups)
    allowed_set = set(g.lower() for g in allowed)
    return len(user_set.intersection(allowed_set)) > 0


# ----------------------------
# Lambda handler
# ----------------------------
def handler(event, context):
    """
    GET /files/list
    1. Authenticate + RBAC check
    2. Scan DynamoDB for all files
    3. Return JSON list
    """
    try:
        # 1️⃣ Auth + RBAC
        cognito = _get_cognito_info_from_event(event)
        groups = cognito.get("groups", [])

        if not groups:
            return _resp(401, {"error": "unauthenticated - no groups"})
        if not _has_any_group(groups, ["admin", "uploader", "viewer"]):
            return _resp(403, {"error": "forbidden - requires viewer/uploader/admin"})

        # 2️⃣ Query DynamoDB
        response = files_table.scan()
        items = response.get("Items", [])

        # 3️⃣ Normalize results
        files = [
            {
                "fileId": item.get("fileId"),
                "key": item.get("s3Key"),
                "filename": item.get("filename"),
                "uploadedAt": item.get("uploadedAt"),
                "uploadedBy": item.get("uploadedBy", "unknown"),
            }
            for item in items
        ]

        return _resp(200, files)

    except Exception as e:
        print("❌ Error listing files:", str(e))
        return _resp(500, {"error": str(e)})
