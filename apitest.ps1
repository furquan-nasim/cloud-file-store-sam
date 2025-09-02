<#
.SYNOPSIS
    Quick test script for calling the SAM API with Cognito authentication.

.DESCRIPTION
    Uses an AccessToken from AWS Cognito to call the protected API Gateway
    endpoints (upload/download/list). This helps confirm that Cognito
    integration (Day 2) is working correctly.

.NOTES
    - Requires you to first obtain an AccessToken using Cognito auth flow
      (see Day 2 steps with `respond-to-auth-challenge`).
    - API URL and token can be passed as parameters, or edited directly below.

.QUICKSTART
    Example usage:

        .\apitest.ps1 -ApiUrl "https://ylh655cllk.execute-api.ap-south-1.amazonaws.com/prod" `
                      -Token "<PasteYourAccessTokenHere>"

    If you don’t pass -ApiUrl, the script will try to fetch it automatically
    from the CloudFormation stack (like outputs.ps1).
#>

param(
    [string]$ApiUrl = "",
    [string]$Token  = ""
)

if (-not $Token) {
    Write-Error "You must provide an AccessToken (use -Token)."
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

# Test 1: List files
Write-Host "`n--- Calling GET /files ---"
try {
    $resp = Invoke-RestMethod -Method GET -Uri "$ApiUrl/files" -Headers @{ Authorization = "Bearer $Token" }
    $resp | ConvertTo-Json -Depth 5
}
catch {
    Write-Error "Failed to call GET /files. $($_.Exception.Message)"
}

# Test 2: Presign upload
Write-Host "`n--- Calling POST /files/presign-upload ---"
try {
    $body = @{ filename = "apitest.txt" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Method POST -Uri "$ApiUrl/files/presign-upload" `
        -Headers @{ Authorization = "Bearer $Token"; "Content-Type"="application/json" } `
        -Body $body
    $resp | ConvertTo-Json -Depth 5
}
catch {
    Write-Error "Failed to call presign-upload. $($_.Exception.Message)"
}
