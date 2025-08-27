#!/usr/bin/env powershell
# Backend Startup Script
# Simple script to start the FastAPI backend

Write-Host "Starting Backend Service..." -ForegroundColor Green

# Navigate to backend directory
Set-Location "backend"

# Activate virtual environment if it exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
}

# Install dependencies if needed
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    & "venv\Scripts\Activate.ps1"
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Start FastAPI server
Write-Host "Starting FastAPI server..." -ForegroundColor Green
python main.py
