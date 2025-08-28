import os
import json
import urllib.parse
import boto3
from botocore.config import Config

REGION = os.environ.get("AWS_REGION", "ap-south-1")

# Force regional endpoint + SigV4 (matches upload)
s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4"),
)

BUCKET = os.environ["BUCKET_NAME"]
TTL = int(os.environ.get("PRESIGN_TTL_SECONDS", "900"))


def _resp(status, body):
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


def handler(event, context):
    try:
        # Defensive extraction of query params
        params = event.get("queryStringParameters") or {}
        if isinstance(params, str):
            # sometimes (rare) comes URL-encoded string
            params = dict(urllib.parse.parse_qsl(params))
        key = params.get("key")

        if not key:
            return _resp(400, {"error": "query parameter 'key' is required"})

        # URL-decode just in case API Gateway encoded slashes (%2F)
        key = urllib.parse.unquote(key)

        presign_params = {"Bucket": BUCKET, "Key": key}
        # Support optional versionId param
        version_id = params.get("versionId")
        if version_id:
            presign_params["VersionId"] = version_id

        url = s3.generate_presigned_url(
            "get_object",
            Params=presign_params,
            ExpiresIn=TTL,
        )

        return _resp(200, {"url": url, "expiresIn": TTL})

    except Exception as e:
        # Make sure we ALWAYS return JSON instead of crashing (which causes API 502)
        return _resp(500, {"error": f"{type(e).__name__}: {str(e)}"})
