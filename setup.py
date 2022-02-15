from setuptools import setup


def get_description():
    with open("README.md") as file:
        return file.read()


setup(
    name="bubble-client",
    version="0.4.0",
    url="https://github.com/Refty/bubble-client",
    author="Guillaume Gelin",
    author_email="guillaume@refty.co",
    description="Python client for Bubble.io APIs",
    long_description=get_description(),
    long_description_content_type="text/markdown",
    py_modules=["bubble_client"],
    python_requires=">=3.7, <4",
    install_requires=[
        "thingy >= 0.8.5",
        "httpx >= 0.21.3",
    ],
    classifiers=[
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
    ],
)
