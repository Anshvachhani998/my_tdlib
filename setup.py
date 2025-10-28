from setuptools import setup, find_packages

setup(
    name="my_tdlib",
    version="1.0.0",
    author="Ansh Vachhani",
    description="Custom Telegram TDLib utilities and downloader",
    packages=find_packages(),
    install_requires=[
        "tgcrypto",  # Always install latest tgcrypto
        "git+https://github.com/TelegramPlayground/pyrogram.git"
    ],
    python_requires=">=3.10",
)
