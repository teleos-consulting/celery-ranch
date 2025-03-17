from setuptools import setup, find_packages

setup(
    name="ranch",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "celery>=5.0.0",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-cov",
            "black",
            "isort",
            "flake8",
            "mypy",
        ],
    },
    author="Claude",
    author_email="example@example.com",
    description="Ranch: A Celery extension providing LRU-based task prioritization",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/username/ranch",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
)
