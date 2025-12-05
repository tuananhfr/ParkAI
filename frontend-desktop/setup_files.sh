#!/bin/bash
# Script to create all necessary files and folders for Phase 1-3

set -e

echo "📦 Creating project structure..."

# Create directories
mkdir -p ui/dashboard
mkdir -p core
mkdir -p utils

# Create __init__.py files
touch ui/__init__.py
touch ui/dashboard/__init__.py
touch core/__init__.py
touch utils/__init__.py

echo "✅ Project structure created!"
echo ""
echo "Now you need to copy the Python files from your development machine."
echo "Or run this script on your development machine and sync to Pi."
