# CypherPulse Installation Script for Windows
# Run in PowerShell as Administrator

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/tibor-ai/cypherpulse.git"
$InstallDir = "$env:USERPROFILE\cypherpulse"
$MinPythonVersion = [version]"3.9.0"

Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   CypherPulse Installation" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check Python version
function Test-PythonVersion {
    try {
        $pythonCmd = Get-Command python -ErrorAction Stop
        $versionOutput = & python --version 2>&1
        $versionString = $versionOutput -replace "Python ", ""
        $version = [version]$versionString
        
        if ($version -ge $MinPythonVersion) {
            Write-Host "✓ Python $versionString found" -ForegroundColor Green
            return $true
        } else {
            Write-Host "⚠ Python $versionString found (need 3.9+)" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Host "⚠ Python not found" -ForegroundColor Yellow
        return $false
    }
}

# Install Python if needed
if (-not (Test-PythonVersion)) {
    Write-Host ""
    Write-Host "Python 3.9+ is required but not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python:" -ForegroundColor Yellow
    Write-Host "  1. Visit: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  2. Download Python 3.11 or newer" -ForegroundColor Yellow
    Write-Host "  3. During installation, check 'Add Python to PATH'" -ForegroundColor Yellow
    Write-Host "  4. Run this script again after installation" -ForegroundColor Yellow
    Write-Host ""
    
    $openBrowser = Read-Host "Open Python download page in browser? (Y/n)"
    if ($openBrowser -ne "n") {
        Start-Process "https://www.python.org/downloads/"
    }
    
    exit 1
}

Write-Host ""

# Clone or update repository
if (Test-Path $InstallDir) {
    Write-Host "📁 CypherPulse directory already exists at $InstallDir" -ForegroundColor Yellow
    $update = Read-Host "Update existing installation? (y/N)"
    
    if ($update -eq "y" -or $update -eq "Y") {
        Write-Host "Updating repository..." -ForegroundColor Cyan
        Push-Location $InstallDir
        
        try {
            if (Get-Command git -ErrorAction SilentlyContinue) {
                git pull origin main
            } else {
                Write-Host "⚠ Git not found, skipping update" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "⚠ Git pull failed, skipping update" -ForegroundColor Yellow
        }
        
        Pop-Location
    } else {
        Write-Host "Skipping repository update" -ForegroundColor Gray
    }
} else {
    Write-Host "📦 Downloading CypherPulse..." -ForegroundColor Cyan
    
    # Try git first, fall back to ZIP download
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Host "Using git to clone repository..." -ForegroundColor Gray
        git clone $RepoUrl $InstallDir
    } else {
        Write-Host "Git not found, downloading ZIP..." -ForegroundColor Yellow
        
        $zipUrl = "https://github.com/tibor-ai/cypherpulse/archive/refs/heads/main.zip"
        $zipPath = "$env:TEMP\cypherpulse.zip"
        
        try {
            Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
            Expand-Archive -Path $zipPath -DestinationPath "$env:TEMP\cypherpulse-temp" -Force
            Move-Item "$env:TEMP\cypherpulse-temp\cypherpulse-main" $InstallDir
            Remove-Item $zipPath
            Remove-Item "$env:TEMP\cypherpulse-temp" -Recurse
        } catch {
            Write-Host "✗ Failed to download repository" -ForegroundColor Red
            exit 1
        }
    }
}

Set-Location $InstallDir
Write-Host ""

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "🐍 Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
    
    if (-not $?) {
        Write-Host "✗ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
}

# Activate and install dependencies
Write-Host "📚 Installing dependencies..." -ForegroundColor Cyan

& "$InstallDir\venv\Scripts\Activate.ps1"

python -m pip install --upgrade pip | Out-Null
python -m pip install -r requirements.txt

if (-not $?) {
    Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Install package in development mode
python -m pip install -e . 2>&1 | Out-Null

Write-Host ""

# Copy config file if needed
if (-not (Test-Path ".env")) {
    Write-Host "⚙️  Creating .env file from template..." -ForegroundColor Cyan
    Copy-Item "config.example.env" ".env"
    Write-Host "✓ .env file created" -ForegroundColor Green
} else {
    Write-Host "✓ .env file already exists (not overwriting)" -ForegroundColor Green
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "✓ Installation complete!" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Get your API key from https://twitterapi.io/" -ForegroundColor White
Write-Host ""
Write-Host "2. Edit your configuration:" -ForegroundColor White
Write-Host "   notepad $InstallDir\.env" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Add your credentials:" -ForegroundColor White
Write-Host "   TWITTER_API_KEY=your_api_key_here" -ForegroundColor Gray
Write-Host "   TWITTER_USERNAME=your_twitter_username" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Start the dashboard:" -ForegroundColor White
Write-Host "   cd $InstallDir" -ForegroundColor Yellow
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "   cypherpulse serve" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Then open: http://localhost:8080" -ForegroundColor White
Write-Host ""
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
