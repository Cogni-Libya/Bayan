#!/bin/bash
# Assemble the Space repo (app + the bayanbench package it imports) in build/, ready for `hf upload`.
set -e
cd "$(dirname "$0")"
rm -rf build && mkdir build
cp app.py requirements.txt README.md build/
cp -r ../src/bayanbench build/bayanbench
find build -name __pycache__ -prune -exec rm -rf {} +
echo "built $(pwd)/build"
