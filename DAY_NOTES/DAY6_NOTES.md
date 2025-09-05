# Day 6 Notes – RBAC & Deletion

## ✅ What we did
- Added `_get_cognito_info_from_event` helper and **RBAC checks** across all Lambda functions:
  - **Presign Upload** → allowed for `uploader`, `admin`.
  - **Presign Download** → allowed for `viewer`, `uploader`, `admin`.
  - **List Files** → allowed for all roles.
  - **Delete File** → allowed for `admin` only.
  - **Record Download** → allowed for `viewer`, `uploader`, `admin`.
- Updated `template.yaml` with necessary IAM policies for each Lambda.
- Created **Cognito groups** (`viewer`, `uploader`, `admin`).
- Created users for each group:
  - `vieweruser@example.com` → can only list & download.
  - `uploaderuser@example.com` → can list, upload, download.
  - `testuser@example.com` (admin) → full rights including delete.
- Successfully tested:
  - Viewer user → could list but upload/delete was denied.
  - Uploader user → could upload and list, delete denied.
  - Admin user → could delete, confirmed DynamoDB row + S3 object removed.

## 🧪 Validation
- `apitest.ps1` used with each role’s IdToken.
- Verified RBAC rules enforced correctly.
- Confirmed file upload, download, listing, and deletion behaviors per role.

## 📊 Status
- Backend + RBAC = **100% complete** ✅
- Remaining (Day 7):
  - Frontend (React/HTML) integration.
  - Documentation (security architecture + deployment guide).
  - Demo video.

---
