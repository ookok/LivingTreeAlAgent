from setuptools import setup, find_packages

setup(
    name="pngjpeg",
    version="1.0.0",
    description="批量转换图片格式工具，支持PNG和JPEG互转",
    author="Hermes-Auto",
    license="MIT",
    packages=find_packages(),
    install_requires=[],
    entry_points={
        "console_scripts": [
            "pngjpeg=cli_tool.__main__:main",
        ]
    },
    python_requires=">=3.10",
)
