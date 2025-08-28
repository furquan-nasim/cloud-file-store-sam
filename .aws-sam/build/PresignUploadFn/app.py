import os, json, uuid, boto3
from botocore.config import Config

REGION = os.environ.get("AWS_REGION", "ap-south-1")
# Force regional endpoint + SigV4
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
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body or "{}")
        filename = body.get("filename")
        if not filename:
            return _resp(400, {"error": "filename is required"})

        file_id = str(uuid.uuid4())
        key = f"uploads/{file_id}/{filename}"

        url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=TTL,
        )

        return _resp(200, {"fileId": file_id, "key": key, "url": url, "expiresIn": TTL})
    except Exception as e:
        return _resp(500, {"error": str(e)})
