# Backup de Postgres (Windows/dev). Uso desde la raíz del repo:
#   powershell -File scripts/backup-db.ps1                 # dev (docker-compose.dev.yml)
#   powershell -File scripts/backup-db.ps1 -Prod
param([switch]$Prod, [string]$Dir = "backups", [int]$KeepDays = 14)
$ErrorActionPreference = "Stop"
$files = if ($Prod) { @("-f", "docker-compose.yml", "-f", "docker-compose.prod.yml") } else { @("-f", "docker-compose.yml", "-f", "docker-compose.dev.yml") }
New-Item -ItemType Directory -Force $Dir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$name = "planilla_$stamp.dump"
# pg_dump dentro del contenedor y copia binaria (evita la corrupción de redirección de PowerShell)
docker compose @files exec -T db sh -c "pg_dump -U planilla -d planilla -Fc -f /tmp/$name && pg_restore -l /tmp/$name > /dev/null"
$cid = docker compose @files ps -q db
docker cp "${cid}:/tmp/$name" (Join-Path $Dir $name)
docker compose @files exec -T db rm -f "/tmp/$name"
Get-ChildItem $Dir -Filter "planilla_*.dump" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } | Remove-Item
Write-Output "OK $(Join-Path $Dir $name) ($([math]::Round((Get-Item (Join-Path $Dir $name)).Length/1KB)) KB)"
