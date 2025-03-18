from setuptools import setup

setup(
    name="celery-ranch",
    version="0.1.0",
    packages=["celery_ranch", "celery_ranch.utils"],
    install_requires=[
        "celery>=5.3.4",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "black>=23.11.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.0",
            "pylint>=3.0.2",
            "redis>=5.0.1",
            "types-redis",
            "types-setuptools",
        ],
        "redis": [
            "redis>=5.0.1",
        ],
    },
    author="Matthew DesEnfants",
    author_email="matt@teleos.ltd",
    description="Celery Ranch: Extension providing LRU-based task prioritization",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/teleos-consulting/celery-ranch",
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
