#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup script para Ferramentas de Rede

Script de instalação e configuração do projeto.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Ler o README
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()

# Ler requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    with open(requirements_path, "r", encoding="utf-8") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="ferramentasderede",
    version="1.1.0",
    author="Sistema de Ferramentas de Rede",
    author_email="contato@ferramentasderede.com",
    description="Aplicação Profissional de Gerenciamento de Redes",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Networking :: Monitoring",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ferramentasderede=ferramentasderede.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "ferramentasderede": [
            "assets/**/*",
            "data/**/*",
        ],
    },
    keywords="network, monitoring, administration, tools, gui",
    project_urls={
        "Documentation": "https://ferramentasderede.readthedocs.io/",
    },
)
