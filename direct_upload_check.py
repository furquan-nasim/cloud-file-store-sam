import boto3, uuid, os

REGION = "ap-south-1"
BUCKET = "<paste your BucketName here>"

s3 = boto3.client("s3", region_name=REGION)

key = f"debug/{uuid.uuid4().hex}.txt"
data = b"hello from direct boto3 put_object"

s3.put_object(Bucket=BUCKET, Key=key, Body=data)
print("put_object OK at key:", key)

obj = s3.get_object(Bucket=BUCKET, Key=key)
print("get_object OK, len:", len(obj["Body"].read()))
