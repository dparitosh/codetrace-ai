#!/usr/bin/env powershell
# Frontend Startup Script
# Simple script to start the React frontend

Write-Host "Starting Frontend Service..." -ForegroundColor Green

# Navigate to frontend directory
Set-Location "frontend"

# Install dependencies if needed
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    npm install
}

# Start development server
Write-Host "Starting React development server..." -ForegroundColor Green
npm run dev
