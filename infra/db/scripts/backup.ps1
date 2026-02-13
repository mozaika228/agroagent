param(
  [string]$OutDir = "infra/db/backups",
  [string]$DbName = "agroagent",
  [string]$DbUser = "agro",
  [string]$DbHost = "localhost",
  [string]$DbPort = "5432"
)

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$file = Join-Path $OutDir "$DbName-$timestamp.dump"

pg_dump -h $DbHost -p $DbPort -U $DbUser -Fc -f $file $DbName
Write-Output "Backup created: $file"
