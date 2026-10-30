# Ejecuta los E2E en un contenedor desechable de Playwright contra el stack local (web :8080).
# Uso (desde la raiz del repo):  powershell -File e2e/run-e2e.ps1
param([string]$BaseUrl = "http://host.docker.internal:8080")
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
docker run --rm --add-host=host.docker.internal:host-gateway -e BASE_URL=$BaseUrl -e E2E_PASSWORD=$env:E2E_PASSWORD `
  -v "${here}:/e2e" -w /e2e mcr.microsoft.com/playwright:v1.48.2-noble `
  sh -c "npm install --no-audit --no-fund --silent && npx playwright test"
