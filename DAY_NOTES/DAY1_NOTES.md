\# Cloud File Store — Day 1 Progress Notes



\## ✅ Goals for Day 1

\- Set up project environment

\- Deploy minimal backend infrastructure (S3, DynamoDB, Lambda, API Gateway)

\- Enable file upload \& download via presigned URLs

\- Validate end-to-end workflow with a smoke test



---



\## 🛠️ Work Done



\### 1. Environment Setup

\- Installed \*\*AWS CLI v2\*\*, \*\*SAM CLI\*\*, and Python (with `.venv` virtual environment).

\- Created project structure under `cloud-file-store-sam/`.

\- Installed Python packages (`boto3`, `requests`).



\### 2. Infrastructure (SAM / CloudFormation)

\- Wrote \*\*template.yaml\*\* including:

&nbsp; - S3 bucket with versioning enabled.

&nbsp; - DynamoDB tables (`FilesTable`, `DownloadHistoryTable`).

&nbsp; - Lambda functions for:

&nbsp;   - `presign\_upload` (generate S3 PUT URLs).

&nbsp;   - `presign\_download` (generate S3 GET URLs).

&nbsp; - API Gateway to expose these Lambda functions.

\- Fixed stack deployment issues:

&nbsp; - DynamoDB BillingMode set to `PAY\_PER\_REQUEST`.

&nbsp; - Corrected S3 + IAM permissions.

\- Deployed successfully with `sam build \&\& sam deploy`.



\### 3. Utilities

\- Created \*\*outputs.ps1\*\*:

&nbsp; - Helper script to quickly fetch stack outputs (API URL, bucket name, DynamoDB table names).

&nbsp; - Added header docs + reminder about `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

\- Created \*\*smoketest.py\*\*:

&nbsp; - Generates a temporary test file (e.g., `test-xxxx.txt`).

&nbsp; - Calls API Gateway → gets presigned upload URL.

&nbsp; - Uploads file to S3.

&nbsp; - Calls API Gateway → gets presigned download URL.

&nbsp; - Downloads file and prints content.



\### 4. Debugging Journey

\- Fixed `403 SignatureDoesNotMatch` by:

&nbsp; - Removing `ContentType` header from presign logic.

&nbsp; - Forcing regional S3 endpoint in Lambdas.

\- Fixed `502 Internal Server Error` in download Lambda by:

&nbsp; - Improving error handling.

&nbsp; - Decoding query parameters properly.

\- After fixes → upload/download roundtrip confirmed ✅.



---



\## 📊 Final Result (End of Day 1)

\- Running `python smoketest.py` produces:

=== Smoke Test ===
File: test-xxxxxx.txt
Upload presign: OK
Upload to S3: OK
Download presign: OK
Download from S3: OK
File content: hello from SAM


- End-to-end flow **works perfectly**.

---

## 🚀 Next Steps (Day 2 Plan)
1. Add **Cognito authentication** (user pool + groups).
2. Implement **metadata writes to DynamoDB** on upload.
3. Add a **list-files Lambda/API** to fetch stored metadata.
4. Build a **minimal React frontend**:
   - Sign in with Cognito.
   - Upload files via presign.
   - List & download uploaded files.

---

> 📌 Day 1 takeaway: Core infrastructure is live, roundtrip upload/download confirmed, environment ready for Day 2 (auth + metadata + UI).
