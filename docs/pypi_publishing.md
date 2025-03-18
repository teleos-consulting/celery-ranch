# Publishing Ranch to PyPI or GitHub

This document provides instructions for publishing the Ranch package to the Python Package Index (PyPI) or making it installable from GitHub.

## Installation from GitHub

While PyPI registrations are temporarily unavailable, you can install the package directly from GitHub using pip:

```bash
# Install the latest version
pip install git+https://github.com/teleos-consulting/celery-ranch.git

# Install a specific version by tag
pip install git+https://github.com/teleos-consulting/celery-ranch.git@v0.1.0

# Install with Redis support
pip install "git+https://github.com/teleos-consulting/celery-ranch.git#egg=celery-ranch[redis]"
```

## Prerequisites for PyPI Publishing

1. You need an account on [PyPI](https://pypi.org/) and/or [TestPyPI](https://test.pypi.org/)
2. Generate API tokens from your PyPI/TestPyPI account settings

## Setup

1. Configure authentication by creating a `.pypirc` file in your home directory:

```
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = your-pypi-token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = your-testpypi-token
```

Alternatively, you can use environment variables:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=your-pypi-token
```

## Publishing Process

We've created a script to handle the publishing workflow. The script:

1. Runs tests
2. Runs linters and type checking
3. Builds package distributions
4. Verifies package quality with Twine
5. Uploads to PyPI or TestPyPI

### Commands

To publish to TestPyPI:

```bash
./scripts/publish.sh --test
```

To publish to PyPI:

```bash
./scripts/publish.sh
```

### Manual Publishing

If you prefer to publish manually:

```bash
# Activate your virtual environment
source venv/bin/activate

# Build distributions
python -m build

# Check distributions
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

## Version Management

The package version is defined in both:
- `ranch/__init__.py` (`__version__` variable)
- `pyproject.toml` (`version` field)

When releasing a new version, make sure to update both locations.

## Versioning Scheme

We follow semantic versioning:
- MAJOR version for incompatible API changes
- MINOR version for backward-compatible functionality additions
- PATCH version for backward-compatible bug fixes

## After Publishing

After successfully publishing, verify the package can be installed:

```bash
# From TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ ranch

# From PyPI
pip install ranch
```