<#
.SYNOPSIS
    Quick test script for calling the SAM API with Cognito authentication.

.DESCRIPTION
    Uses an IdToken from AWS Cognito to call the protected API Gateway
    endpoints (list, upload). Confirms Cognito integration (Day 2) and
    file listing functionality (Day 3).

.NOTES
    - Requires you to first obtain an IdToken (NOT AccessToken) using Cognito.
    - API URL and token can be passed as parameters, or fetched from stack.
    - Runs three tests:
        1. GET /files            (basic auth check – may fail if not mapped)
        2. GET /files/list       (Day 3 – list files in S3)
        3. POST /files/presign-upload (Day 1 + 2 – presign upload)

.QUICKSTART
    Example usage:

        .\apitest.ps1 -Token "<PasteYourIdTokenHere>"

    Or with explicit API URL:

        .\apitest.ps1 -ApiUrl "https://yourapi.execute-api.ap-south-1.amazonaws.com/prod" `
                      -Token "<PasteYourIdTokenHere>"
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
# 1. GET /files (legacy – not mapped in Day 3, may return 403)
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
# 2. GET /files/list (Day 3 – should succeed and return file list)
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
# 3. POST /files/presign-upload (Day 1 + 2 – generate presign URL)
# -------------------------------------------------------------------------
Write-Host "`n--- Calling POST /files/presign-upload ---"
try {
    $body = @{ filename = "apitest.txt" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Method POST -Uri "$ApiUrl/files/presign-upload" `
        -Headers @{ Authorization = "Bearer $Token"; "Content-Type"="application/json" } `
        -Body $body
    Write-Host "✅ presign-upload succeeded:" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5
}
catch {
    Write-Error "❌ presign-upload failed: $($_.Exception.Message)"
}
