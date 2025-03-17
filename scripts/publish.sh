#!/bin/bash
set -e

# Activate virtual environment
source venv/bin/activate

# Clean up previous builds
rm -rf build/ dist/ *.egg-info/

# Run tests
echo "Running tests..."
pytest

# Run linters and type checking
echo "Running linters and type checking..."
flake8 ranch
pylint ranch
mypy .

# Build package
echo "Building package..."
python -m build

# Check package
echo "Checking distribution with twine..."
twine check dist/*

# Upload to TestPyPI (optional)
if [ "$1" == "--test" ]; then
  echo "Uploading to TestPyPI..."
  twine upload --repository testpypi dist/*
  echo "Package uploaded to TestPyPI. Install with:"
  echo "pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ranch"
  exit 0
fi

# Upload to PyPI
echo "Uploading to PyPI..."
twine upload dist/*

echo "Package published successfully!"