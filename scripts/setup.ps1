# Circlo Safety Development Setup Script (PowerShell)

Write-Host "Setting up Circlo Safety development environment..." -ForegroundColor Green

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if Docker Compose is available
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "Docker Compose is not available. Please ensure Docker Desktop is properly installed." -ForegroundColor Red
    exit 1
}

# Create .env file from example if it doesn't exist
if (-not (Test-Path "backend/.env")) {
    Write-Host "Creating backend/.env from .env.example..." -ForegroundColor Yellow
    Copy-Item "backend/.env.example" "backend/.env"
}

# Start Docker containers
Write-Host "Starting Docker containers..." -ForegroundColor Yellow
docker-compose up -d

# Wait for database to be ready
Write-Host "Waiting for database to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Install Python dependencies (if running locally)
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    Push-Location backend
    python -m pip install -r requirements.txt
    Pop-Location
}

# Install Flutter dependencies (if Flutter is installed)
if (Get-Command flutter -ErrorAction SilentlyContinue) {
    Write-Host "Installing Flutter dependencies..." -ForegroundColor Yellow
    Push-Location mobile
    flutter pub get
    Pop-Location
}

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Services running:" -ForegroundColor Cyan
Write-Host "  - Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "  - PostgreSQL: localhost:5432" -ForegroundColor White
Write-Host "  - Redis: localhost:6379" -ForegroundColor White
Write-Host ""
Write-Host "To run tests:" -ForegroundColor Cyan
Write-Host "  Backend: cd backend && pytest" -ForegroundColor White
Write-Host "  Mobile: cd mobile && flutter test" -ForegroundColor White
Write-Host ""
Write-Host "To stop services:" -ForegroundColor Cyan
Write-Host "  docker-compose down" -ForegroundColor White
