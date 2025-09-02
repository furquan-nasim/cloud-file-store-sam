# 📌 Day 2 Notes – Adding Cognito Authentication & Role Groups

## ✅ What we achieved today
We extended our Day 1 base (S3 + DynamoDB + Lambda + API) with secure **authentication** and **role-based access control** using Amazon Cognito.  

---

## 🔑 Step-by-Step Progress

### 1. Template Update
- Added **Cognito User Pool**.
- Added **User Pool Client**.
- Created **3 groups**:
  - **admin** → full access
  - **uploader** → upload files
  - **viewer** → read/download only
- Configured **API Gateway** to use Cognito authorizer as default.

### 2. Deployment
- Ran:
  ```powershell
  sam build
  sam deploy --guided
- CloudFormation deployed Cognito resources alongside existing stack.

### 3. Verified Outputs

    Ran:

        .\outputs.ps1


    Confirmed new outputs:

        UserPoolId
        UserPoolClientId

### 4. Created a Test User

Created a user:

    aws cognito-idp admin-create-user `
    --user-pool-id <UserPoolId> `
    --username testuser@example.com `
    --temporary-password TempPassw0rd! `
    --user-attributes Name=email,Value=testuser@example.com `
    --region ap-south-1

- Completed NEW_PASSWORD_REQUIRED challenge to set a permanent password.
- Received ID token and Access token.

### 5. Tested API Access

- Created helper script apitest.ps1 to test API with tokens.

Results:

    GET /files → 403 Forbidden (user not in group yet).

    POST /files/presign-upload → 401 Unauthorized.

### 6. Assigned User to Group

Added user to viewer group:

    aws cognito-idp admin-add-user-to-group `
    --user-pool-id <UserPoolId> `
    --username testuser@example.com `
    --group-name viewer `
    --region ap-south-1

Verified with:

    aws cognito-idp admin-list-groups-for-user `
    --user-pool-id <UserPoolId> `
    --username testuser@example.com `
    --region ap-south-1


- Output confirmed user is in viewer group.

---

📊 Outcome

- Authentication with Cognito works.
- Role-based groups (admin, uploader, viewer) are set up.
- Test user successfully created and assigned to a group.
- API correctly enforces permissions:
    No group = blocked.
    Viewer = download-only (upload restricted).

---

🚀 Next Step (Day 3 Preview)

- Implement real logic in GET /files Lambda.

- List files stored in DynamoDB FilesTable.

- Return metadata to authenticated users depending on role.

📌 Day 2 takeaway: Authentication is live with Cognito. Users and groups (admin, uploader, viewer) are set up. API now enforces role-based access. Ready for Day 3 (file listing + metadata).