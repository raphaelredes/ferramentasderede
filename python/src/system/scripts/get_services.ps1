
Get-Service | Select-Object Name, DisplayName, Status, StartType | ConvertTo-Json -Compress
