# 📖 Day 3 Notes – List Files API

## ✅ What we did today
1. **Extended the SAM template (`template.yaml`)**
   - Added a new Lambda function `ListFilesFn`.
   - Mapped it to the `GET /files/list` API endpoint.
   - Gave it read permissions on the `FilesTable`.

2. **Implemented Lambda code**
   - Created `src/list_files/app.py`.
   - Lambda scans the `FilesTable` and returns all file metadata.
   - Added error handling and CORS headers.

3. **Deployed the stack**
   - Ran `sam build` and `sam deploy` successfully.
   - CloudFormation updated the API and deployed the new Lambda.

4. **Tested with `apitest.ps1`**
   - `GET /files` → returns **403 Forbidden** (expected, since endpoint not implemented).
   - `GET /files/list` → returned **200 OK** ✅.
   - `POST /files/presign-upload` → still works fine, S3 presigned URL returned.

---

## 🔍 Observations
- The `/files/list` endpoint works, but returns an **empty list**.  
- This is expected because we **aren’t saving metadata into DynamoDB yet**.  
- Uploads currently go **only to S3** — DynamoDB will be integrated in **Day 4**.

---

## 📌 Day 3 takeaway
We now have a **working list endpoint** wired to DynamoDB.  
Next, in **Day 4**, we’ll:
- Enhance `presign_upload` Lambda to also insert metadata (`fileId`, `s3Key`, `uploadedAt`) into DynamoDB.
- Verify that `/files/list` returns actual file records.

---
