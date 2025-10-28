# my_tdlib/config.py
from pytdbot import Client, types

def get_client(api_id, api_hash, token, encryption_key="1234_ast$"):
    """
    Create a TDLib client instance with provided credentials.
    All parameters are required except encryption_key.
    """
    if not api_id or not api_hash or not token:
        raise ValueError("❌ Missing required TDLib credentials (api_id, api_hash, or token).")

    return Client(
        token=token,
        api_id=api_id,
        api_hash=api_hash,
        files_directory="TDLibFiles",
        database_encryption_key=encryption_key,
        td_verbosity=1,
        td_log=types.LogStreamFile("tdlib.log", 104857600),
    )
