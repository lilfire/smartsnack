# Check if Docker is running
docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}

Write-Host "Stopping containers..." -ForegroundColor Cyan
docker-compose down

Write-Host "Rebuilding and starting containers..." -ForegroundColor Cyan
$env:DOCKER_BUILDKIT = "1"
$env:COMPOSE_DOCKER_CLI_BUILD = "1"
docker-compose up --build -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "Done! Containers rebuilt successfully." -ForegroundColor Green
} else {
    Write-Host "Build failed. Check the errors above." -ForegroundColor Red
    exit 1
}