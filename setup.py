from setuptools import setup, find_packages

setup(
    name="my_tdlib",
    version="1.0.0",
    author="Ansh Vachhani",
    description="Custom Telegram TDLib utilities and downloader",
    packages=find_packages(),
    install_requires=[
        "pyrogram<=2.0.33",
        "tgcrypto<=1.2.3"
    ],
    python_requires=">=3.8",
)
