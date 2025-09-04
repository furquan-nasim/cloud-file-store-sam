# 📅 Day 5 Notes – File Download Flow

## ✅ What we achieved today
- Created and implemented **Presign Download Lambda** (`src/presign_download/app.py`).
- Updated `template.yaml`:
  - Added correct IAM policies (`S3ReadPolicy`, `DynamoDBCrudPolicy`, etc.).
  - Ensured the Lambda has access to S3 and metadata tables.
- Built & deployed successfully with `sam build && sam deploy`.
- Extended `apitest.ps1` to exercise the new download endpoint.
- Verified full **file lifecycle**:
  1. Upload → get presigned PUT URL, save file to S3.
  2. List → confirm file metadata appears via DynamoDB.
  3. Download → get presigned GET URL and retrieve file back from S3.

## 🔍 Key learnings
- Presign download URLs need query parameters (`key`, `versionId`, etc.).
- Optional content-disposition headers (`downloadName`, `asAttachment`) improve UX.
- HEAD-checking objects before generating presigned URLs helps return clean 404s.
- Full round-trip of file **upload → list → download** is working end-to-end.

## 📌 Day 5 takeaway
The core storage workflow is complete.  
Users can now **upload, browse, and download files** securely using Cognito-authenticated APIs.
