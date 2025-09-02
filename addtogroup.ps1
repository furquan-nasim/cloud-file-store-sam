<#
.SYNOPSIS
    Add a Cognito user to a specific group.

.DESCRIPTION
    This helper script makes it easier to assign users to Cognito groups 
    without typing the long AWS CLI command each time.

.PARAMETER User
    The username (usually email) of the user to add.

.PARAMETER Group
    The Cognito group name (e.g., Viewer, Uploader, Admin).

.PARAMETER PoolId
    The Cognito User Pool ID. Defaults to Day 2 pool: "ap-south-1_QSETpyYOL".

.PARAMETER Region
    AWS region where the pool exists. Defaults to "ap-south-1".

.EXAMPLE
    # Add a user to Viewer group
    .\addtogroup.ps1 -User testuser@example.com -Group Viewer

.EXAMPLE
    # Add a user to Uploader group in custom pool
    .\addtogroup.ps1 -User another@example.com -Group Uploader -PoolId ap-south-1_ABC123

.NOTES
    Requires AWS CLI v2 configured with appropriate credentials.
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$User,

    [Parameter(Mandatory=$true)]
    [string]$Group,

    [string]$PoolId = "ap-south-1_QSETpyYOL",
    [string]$Region = "ap-south-1"
)

Write-Host "👉 Adding user '$User' to group '$Group' in pool '$PoolId' ($Region)..."

try {
    aws cognito-idp admin-add-user-to-group `
        --user-pool-id $PoolId `
        --username $User `
        --group-name $Group `
        --region $Region

    Write-Host "✅ User '$User' successfully added to group '$Group'."

    Write-Host "`n📌 Current groups for $User:"
    aws cognito-idp admin-list-groups-for-user `
        --user-pool-id $PoolId `
        --username $User `
        --region $Region
}
catch {
    Write-Error "❌ Failed to add user. Details: $($_.Exception.Message)"
}
