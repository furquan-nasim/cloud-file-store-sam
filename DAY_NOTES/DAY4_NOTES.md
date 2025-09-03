# 📌 Day 4 Notes – File Metadata Persistence

## ✅ What we achieved today
- **Extended Presign Upload Lambda (`src/presign_upload/app.py`)**
  - Each time a file is uploaded, we now write a record into **DynamoDB (FilesTable)**.
  - Metadata stored:  
    - `fileId` → UUID for each file  
    - `s3Key` → the exact S3 path where it’s stored  
    - `uploadedAt` → timestamp of the upload  

- **Updated `template.yaml`**
  - Gave `PresignUploadFn` permissions to write into `FilesTable`.  
  - Confirmed SAM build + deploy worked fine.  

- **Enhanced testing flow (`apitest.ps1`)**
  - Script now does **end-to-end validation**:  
    1. Calls `POST /files/presign-upload` → gets presigned URL  
    2. Uploads the file to S3 using the URL  
    3. Re-checks `GET /files/list` → sees the file metadata appear from DynamoDB  
  - Verified file shows up with `fileId`, `key`, and `uploadedAt`.  

---

## 🧪 Test run example
- **presign-upload succeeded** → generated S3 presigned URL  
- **File uploaded successfully** → S3 PUT request worked  
- **Re-check list succeeded** → DynamoDB record appeared:
```json
{
  "fileId": "2677575c-4254-4447-adf7-4de1719bbd7d",
  "key": "uploads/2677575c-4254-4447-adf7-4de1719bbd7d/apitest.txt",
  "uploadedAt": "2025-09-03T21:47:18.861471"
}
