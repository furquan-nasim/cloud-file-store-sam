<#
.SYNOPSIS
    Test script for calling the SAM API with Cognito authentication.

.DESCRIPTION
    Uses an IdToken from AWS Cognito to call the protected API Gateway
    endpoints (list, upload). Confirms Cognito integration (Day 2),
    file listing functionality (Day 3), and optionally performs a real
    S3 upload using the presigned URL.

.NOTES
    - Requires you to first obtain an IdToken (NOT AccessToken).
    - API URL and token can be passed as parameters, or fetched from stack.
    - Runs 4 tests:
        1. GET /files (legacy – may fail)
        2. GET /files/list (Day 3 – list files in DynamoDB)
        3. POST /files/presign-upload (Day 1/2 – get presign URL)
        4. [NEW] Upload test file to S3 using presign URL, then re-list
#>

param(
    [string]$ApiUrl = "",
    [string]$Token  = ""
)

# -------------------------------------------------------------------------
# 0. Validate input
# -------------------------------------------------------------------------
if (-not $Token) {
    Write-Error "❌ You must provide an IdToken (use -Token)."
    exit 1
}

# If no ApiUrl provided, try to get it from CloudFormation outputs
if (-not $ApiUrl) {
    $stack   = "cloud-file-store-sam"
    $region  = "ap-south-1"
    $resp    = aws cloudformation describe-stacks --stack-name $stack --region $region | ConvertFrom-Json
    $outputs = @{}
    $resp.Stacks[0].Outputs | ForEach-Object { $outputs[$_.OutputKey] = $_.OutputValue }
    $ApiUrl = $outputs['ApiUrl']
}

Write-Host "Using API: $ApiUrl"
Write-Host "Token (truncated): $($Token.Substring(0,25))..."

# -------------------------------------------------------------------------
# 1. GET /files
# -------------------------------------------------------------------------
Write-Host "`n--- Calling GET /files ---"
try {
    $resp = Invoke-RestMethod -Method GET -Uri "$ApiUrl/files" -Headers @{ Authorization = "Bearer $Token" }
    Write-Host "✅ GET /files succeeded:" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5
}
catch {
    Write-Error "❌ GET /files failed: $($_.Exception.Message)"
}

# -------------------------------------------------------------------------
# 2. GET /files/list
# -------------------------------------------------------------------------
Write-Host "`n--- Calling GET /files/list ---"
try {
    $resp = Invoke-RestMethod -Method GET -Uri "$ApiUrl/files/list" -Headers @{ Authorization = "Bearer $Token" }
    Write-Host "✅ GET /files/list succeeded:" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5
}
catch {
    Write-Error "❌ GET /files/list failed: $($_.Exception.Message)"
}

# -------------------------------------------------------------------------
# 3. POST /files/presign-upload
# -------------------------------------------------------------------------
Write-Host "`n--- Calling POST /files/presign-upload ---"
$presign = $null
try {
    $body = @{ filename = "apitest.txt" } | ConvertTo-Json
    $presign = Invoke-RestMethod -Method POST -Uri "$ApiUrl/files/presign-upload" `
        -Headers @{ Authorization = "Bearer $Token"; "Content-Type"="application/json" } `
        -Body $body
    Write-Host "✅ presign-upload succeeded:" -ForegroundColor Green
    $presign | ConvertTo-Json -Depth 5
}
catch {
    Write-Error "❌ presign-upload failed: $($_.Exception.Message)"
}

# -------------------------------------------------------------------------
# 4. OPTIONAL: Upload a real file to S3 via presigned URL
# -------------------------------------------------------------------------
if ($presign -and $presign.url) {
    Write-Host "`n--- Uploading file to S3 using presigned URL ---"
    try {
        # Create a dummy file if it doesn’t exist
        $localFile = "apitest.txt"
        if (-not (Test-Path $localFile)) {
            "Hello from apitest.ps1 at $(Get-Date)" | Out-File $localFile -Encoding utf8
        }

        # Upload file with PUT to presigned URL
        Invoke-RestMethod -Method PUT -Uri $presign.url -InFile $localFile -ContentType "text/plain"
        Write-Host "✅ File uploaded to S3 successfully" -ForegroundColor Green

        # Re-check file listing
        Write-Host "`n--- Re-checking GET /files/list ---"
        $resp = Invoke-RestMethod -Method GET -Uri "$ApiUrl/files/list" -Headers @{ Authorization = "Bearer $Token" }
        $resp | ConvertTo-Json -Depth 5
    }
    catch {
        Write-Error "❌ File upload failed: $($_.Exception.Message)"
    }
}
else {
    Write-Host "⚠️ Skipping file upload (no presign URL)."
}
