param(
  [Parameter(Mandatory=$true)] [string]$BackupFile,
  [string]$DbName = "agroagent",
  [string]$DbUser = "agro",
  [string]$DbHost = "localhost",
  [string]$DbPort = "5432"
)

pg_restore -h $DbHost -p $DbPort -U $DbUser -d $DbName --clean --if-exists $BackupFile
Write-Output "Restore completed from: $BackupFile"
