#!/bin/bash

set -e

echo "🔍 Checking for Python 3..."
if ! command -v python3 &> /dev/null; then
  echo "📦 Installing python3..."
  sudo apt update
  sudo apt install -y python3
else
  echo "✅ python3 is already installed."
fi

echo "🔍 Checking for pip3..."
if ! command -v pip3 &> /dev/null; then
  echo "📦 Installing python3-pip..."
  sudo apt install -y python3-pip
else
  echo "✅ pip3 is already installed."
fi

echo "🚀 Running Python bootstrap script..."
python3 bootstrap_shadowserver_environment.py
