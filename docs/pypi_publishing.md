# Publishing Ranch to PyPI or GitHub

This document provides instructions for publishing the Ranch package to the Python Package Index (PyPI) or making it installable from GitHub.

## Installation from GitHub

You can install the package directly from GitHub using pip:

```bash
# Install the latest version
pip install git+https://github.com/teleos-consulting/celery-ranch.git

# Install a specific version by tag
pip install git+https://github.com/teleos-consulting/celery-ranch.git@v0.1.1

# Install with Redis support
pip install "git+https://github.com/teleos-consulting/celery-ranch.git#egg=celery-ranch[redis]"
```

## Installation from PyPI

Once published to PyPI, you can install the package with:

```bash
# Install the basic package
pip install celery-ranch

# Install with Redis support
pip install celery-ranch[redis]
```

## Publishing to PyPI via GitHub Actions

The package is configured to publish to PyPI automatically using GitHub Actions with OpenID Connect authentication. This method is secure and doesn't require storing API tokens as GitHub secrets.

### Setup Requirements

1. A repository environment called `pypi` must be configured in your GitHub repository settings.
2. PyPI must be configured to trust GitHub Actions as an OpenID Connect provider.

### Publishing Process

There are two ways to trigger the publishing workflow:

1. **Creating a GitHub Release** (Recommended)
   - Create a new release in GitHub with a tag that matches the version in the code (e.g., `v0.1.1`)
   - The workflow will automatically build and publish the package

2. **Manual Workflow Trigger**
   - Go to the Actions tab in GitHub
   - Select the "Build and Publish Python Package" workflow
   - Click "Run workflow"
   - Enter the version (must match the version in the code)

### Versioning Scheme

We follow semantic versioning:
- MAJOR version for incompatible API changes
- MINOR version for backward-compatible functionality additions
- PATCH version for backward-compatible bug fixes

The package version is defined in both:
- `ranch/__init__.py` (`__version__` variable)
- `celery_ranch/__init__.py` (`__version__` variable) 
- `pyproject.toml` (`version` field)

When releasing a new version, make sure to update all three locations.

## Manual Publishing (Alternative Method)

If you need to publish manually (not recommended):

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

## After Publishing

After successfully publishing, verify the package can be installed:

```bash
# From TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ celery-ranch

# From PyPI
pip install celery-ranch
```

## Troubleshooting

If the GitHub Actions workflow fails:

1. Check that all version numbers match in the three required locations
2. Verify that the PyPI environment is properly configured
3. Ensure tests and linting pass locally before pushing
4. Check for any rate limiting or permission issues with PyPI