from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Single source of truth for version — always read from __init__.py
def get_version():
    import re
    with open("cypherpulse/__init__.py") as f:
        match = re.search(r'^__version__ = ["\']([^"\']+)["\']', f.read(), re.M)
        if match:
            return match.group(1)
    raise RuntimeError("Cannot find version in cypherpulse/__init__.py")

setup(
    name="cypherpulse",
    version=get_version(),
    author="CypherPulse Contributors",
    description="Open-source X/Twitter analytics dashboard",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tibor-ai/cypherpulse",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "cypherpulse=cypherpulse.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "cypherpulse": ["../web/*", "../web/assets/*"],
    },
)
