from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="spacesync",
    version="0.1.0",
    author="SpaceSync Team",
    author_email="info@spacesync.example.com",
    description="A multi-account tracker scanning tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/spacesync",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "python-dotenv>=0.19.0",
        "sqlalchemy>=1.4.0",
        "psycopg2-binary>=2.9.0",
        # Assuming spacemodels is installed separately
        "python-gitlab",
        "flask>=2.0.0",
        "APScheduler>=3.0.0",
        "pytz>=2025.2",
    ],
    entry_points={
        "console_scripts": [
            "spacesync=spacesync.cli.commands:run",
        ],
    },
)
