
Get-Service -Name '__SERVICE_NAME__' -ErrorAction SilentlyContinue | 
Select-Object Name, DisplayName, Status, StartType | 
ConvertTo-Json -Compress
