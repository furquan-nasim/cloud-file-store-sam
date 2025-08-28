import boto3, requests, uuid

STACK, REGION = "cloud-file-store-sam", "ap-south-1"
cf = boto3.client("cloudformation", region_name=REGION)

# Get stack outputs
outs = {o["OutputKey"]: o["OutputValue"] for o in cf.describe_stacks(StackName=STACK)["Stacks"][0]["Outputs"]}
api = outs["ApiUrl"]

# Make a unique test file
name = f"test-{uuid.uuid4().hex[:6]}.txt"
open(name, "w", encoding="utf-8").write("hello from SAM")

print("\n=== Smoke Test ===")
print("File:", name)

# 1) Presign upload
u = requests.post(f"{api}/files/presign-upload", json={"filename": name})
u.raise_for_status()
upload = u.json()
print("Upload presign: OK")

# 2) Upload to S3
put = requests.put(upload["url"], data=open(name, "rb"))
put.raise_for_status()
print("Upload to S3:   OK")

# 3) Presign download
d = requests.get(f"{api}/files/presign-download", params={"key": upload["key"]})
d.raise_for_status()
dl = d.json()
print("Download presign: OK")

# 4) Download from S3
get = requests.get(dl["url"])
get.raise_for_status()
print("Download from S3: OK")

# 5) Show file content
print("File content:", get.text.strip())
