"""Setup script for SpaceModels."""

from setuptools import find_packages, setup

setup(
    name="spacemodels",
    version="0.1.0",
    description="SQLAlchemy ORM models for SpaceBridge ecosystem",
    author="SpaceCode Team",
    author_email="info@spacecode.com",
    url="https://github.com/spacecode/spacemodels",
    packages=find_packages(exclude=["tests", "docs"]),
    python_requires=">=3.9",
    include_package_data=True,
    package_data={"spacemodels": ["py.typed"]},
    install_requires=[
        "sqlalchemy>=2.0.0",
        "psycopg>=3.0.0",
        "pydantic>=2.0.0",
        "typing-extensions>=4.0.0",
        "python-dotenv>=1.0.0",
        "loguru>=0.6.0",
        "passlib>=1.7.4",
        "uuid>=0.0.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
            "flake8>=6.0.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.13",
    ],
)
