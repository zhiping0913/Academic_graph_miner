"""
Academic Graph Miner - Setup Configuration
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="academic-graph-miner",
    version="4.0.0",
    author="Claude Code",
    author_email="claude@example.com",
    description="Automated academic citation network miner with paper downloading and knowledge graph visualization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zhiping0913/Academic_graph_miner",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "academic-graph-miner=main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
