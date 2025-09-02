<#
.SYNOPSIS
    Fetch CloudFormation stack outputs for the SAM project.

.DESCRIPTION
    Helper to quickly print the key outputs (ApiUrl, S3 bucket, DynamoDB tables, Cognito)
    from the deployed CloudFormation stack for this project.

.NOTES
    - Default Stack: "cloud-file-store-sam"
    - Default Region: ap-south-1 (override with -Region if needed)
    - Optional -Profile to select a named AWS CLI profile.

.QUICKSTART
    ⚠️ On some Windows setups, PowerShell blocks scripts by default.

    If you see "running scripts is disabled" error:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

    Then run:
        .\outputs.ps1 -Region ap-south-1
    Or (if you use profiles):
        .\outputs.ps1 -Region ap-south-1 -Profile default
#>

param(
    [string]$Stack   = "cloud-file-store-sam",
    [string]$Region  = "ap-south-1",
    [string]$Profile = ""
)

# Build base AWS CLI args
$awsArgs = @("cloudformation","describe-stacks","--region",$Region,"--stack-name",$Stack)
if ($Profile -ne "") { $awsArgs += @("--profile",$Profile) }

try {
    $resp = & aws @awsArgs | ConvertFrom-Json
    if (-not $resp.Stacks) {
        Write-Error "Stack '$Stack' not found in region '$Region'. Try: .\outputs.ps1 -Region ap-south-1"
        return
    }
    $map = @{}
    $resp.Stacks[0].Outputs | ForEach-Object { $map[$_.OutputKey] = $_.OutputValue }

    $rows = @(
        [pscustomobject]@{ Key="ApiUrl";           Value=$map['ApiUrl'] }
        [pscustomobject]@{ Key="BucketName";       Value=$map['BucketName'] }
        [pscustomobject]@{ Key="FilesTableName";   Value=$map['FilesTableName'] }
        [pscustomobject]@{ Key="HistoryTableName"; Value=$map['HistoryTableName'] }
        [pscustomobject]@{ Key="UserPoolId";       Value=$map['UserPoolId'] }
        [pscustomobject]@{ Key="UserPoolClientId"; Value=$map['UserPoolClientId'] }
    )
    $rows | Format-Table -AutoSize
}
catch {
    Write-Error "Failed to fetch outputs. Details: $($_.Exception.Message)"
    Write-Host "Hint: Check region/profile:"
    Write-Host "  .\outputs.ps1 -Region ap-south-1"
    Write-Host "  .\outputs.ps1 -Region ap-south-1 -Profile default"
}
