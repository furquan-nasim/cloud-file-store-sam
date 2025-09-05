# src/delete_file/app.py
"""
Delete a file (DELETE /files/{fileId})

Flow:
  1. Extract fileId from path parameters
  2. Extract Cognito info from the request and enforce RBAC (admin only)
  3. Lookup file metadata in FilesTable to obtain s3Key
  4. Delete S3 object
  5. Delete metadata item from FilesTable
  6. Return JSON confirmation

Environment:
  - BUCKET_NAME
  - FILES_TABLE_NAME
"""
import os
import json
import boto3
from typing import Any, Dict, List

# ----------------------------
# AWS clients
# ----------------------------
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET = os.environ["BUCKET_NAME"]
FILES_TABLE_NAME = os.environ["FILES_TABLE_NAME"]
files_table = dynamodb.Table(FILES_TABLE_NAME)


# ----------------------------
# Helpers
# ----------------------------
def _resp(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Consistent JSON + CORS response for API Gateway."""
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
    Extract basic Cognito info from the API Gateway event.
    Returns a dict with username/email and groups list.
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


def _is_admin(groups: List[str]) -> bool:
    """Return True if user is in the admin group."""
    if not groups:
        return False
    return any(g.lower() == "admin" for g in groups)


# ----------------------------
# Lambda handler
# ----------------------------
def handler(event, context):
    """
    DELETE /files/{fileId}
    Path parameter: fileId
    Only admins allowed to delete.
    """
    try:
        # 1) Path parameter extraction
        path_params = event.get("pathParameters") or {}
        file_id = path_params.get("fileId") or path_params.get("id") or None
        if not file_id:
            return _resp(400, {"error": "missing path parameter 'fileId'"})

        # 2) Auth + RBAC
        cognito = _get_cognito_info_from_event(event)
        groups = cognito.get("groups", [])
        if not _is_admin(groups):
            return _resp(403, {"error": "admin only"})

        # 3) Lookup metadata in DynamoDB
        resp = files_table.get_item(Key={"fileId": file_id})
        item = resp.get("Item")
        if not item:
            return _resp(404, {"error": "file metadata not found", "fileId": file_id})

        s3_key = item.get("s3Key")
        # Defensive: ensure we have a key
        if not s3_key:
            return _resp(500, {"error": "file metadata missing s3Key", "fileId": file_id})

        # 4) Delete S3 object (best effort: if object missing, continue but report)
        try:
            s3.delete_object(Bucket=BUCKET, Key=s3_key)
        except Exception as s3_err:
            # Log and continue - still attempt to delete metadata
            print(f"Warning: failed to delete S3 object {s3_key}: {s3_err}")

        # 5) Delete metadata from DynamoDB
        try:
            files_table.delete_item(Key={"fileId": file_id})
        except Exception as ddb_err:
            # If metadata deletion fails, report failure
            print(f"Error deleting metadata for {file_id}: {ddb_err}")
            return _resp(500, {"error": f"failed to delete metadata: {str(ddb_err)}", "fileId": file_id})

        # 6) Success response
        return _resp(200, {"deleted": True, "fileId": file_id, "s3Key": s3_key})

    except Exception as e:
        print("Error in delete_file:", str(e))
        return _resp(500, {"error": str(e)})
