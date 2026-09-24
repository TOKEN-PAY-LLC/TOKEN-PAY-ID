from pathlib import Path
from setuptools import setup, find_packages

readme = Path(__file__).resolve().parents[2] / "README.md"

setup(
    name="tokenpay-id",
    version="1.0.1",
    description="Official Python SDK for TOKEN PAY ID — unified authentication platform",
    long_description=readme.read_text(encoding="utf-8") if readme.exists() else "TOKEN PAY ID Python SDK",
    long_description_content_type="text/markdown",
    author="TOKEN PAY LLC",
    author_email="info@tokenpay.space",
    url="https://github.com/TOKEN-PAY-LLC/TOKEN-PAY-ID",
    packages=find_packages(),
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Security",
    ],
)
