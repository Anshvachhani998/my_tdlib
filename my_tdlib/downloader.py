# my_tdlib/downloader.py

import asyncio
import time
from .utils import format_size, format_time
from .config import get_client
import logging


class TDDownloader:
    def __init__(self, api_id, api_hash, token, encryption_key="1234_ast$"):
        """
        Initialize the TDDownloader with mandatory TDLib credentials.
        """
        self.client = get_client(api_id, api_hash, token, encryption_key)

    async def download_file(self, file_id, file_name, *, on_progress=None):
        """
        Download file from Telegram using TDLib.
        Calls on_progress(file_name, downloaded, total, percent, speed, eta)
        but does not send or edit any Telegram messages.
        """
        start = time.time()
        last_time, last_downloaded = start, 0

        result = await self.client.invoke({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 32,
            "offset": 0,
            "limit": 0,
            "synchronous": False,
        })

        fid = getattr(result, "id", result.get("id", None))
        if not fid:
            raise ValueError("⚠️ Invalid file ID or TDLib response.")

        while True:
            f = await self.client.invoke({"@type": "getFile", "file_id": fid})

            # ✅ Download complete
            if getattr(f.local, "is_downloading_completed", False):
                if on_progress:
                    await on_progress(file_name, f.expected_size, f.expected_size, 100.0, 0, 0)
                break

            # 🧮 Calculate progress
            downloaded = getattr(f.local, "downloaded_size", 0)
            total = getattr(f, "expected_size", 0)
            if total == 0:
                await asyncio.sleep(0.5)
                continue

            now = time.time()
            diff = now - last_time
            speed = (downloaded - last_downloaded) / diff if diff > 0 else 0
            percent = (downloaded / total) * 100
            eta = (total - downloaded) / speed if speed > 0 else 0

            # 🔁 Call callback (no message inside lib)
            if on_progress:
                try:
                    await on_progress(file_name, downloaded, total, percent, speed, eta)
                except Exception as e:
                    logging.warning(f"⚠️ Progress callback error: {e}")

            last_time, last_downloaded = now, downloaded
            await asyncio.sleep(0.5)

        logging.info(f"✅ Download complete: {file_name}")
        return f.local.path

    async def upload_file(self, chat_id, file_path, caption="", file_type="document"):
        """
        Upload file to Telegram using TDLib.
        """
        types_map = {
            "document": "inputMessageDocument",
            "photo": "inputMessagePhoto",
            "video": "inputMessageVideo",
            "audio": "inputMessageAudio"
        }
        input_type = types_map.get(file_type, "inputMessageDocument")

        content = {
            "@type": input_type,
            file_type: {"@type": "inputFileLocal", "path": file_path},
            "caption": {"@type": "formattedText", "text": caption},
        }

        await self.client.invoke({
            "@type": "sendMessage",
            "chat_id": chat_id,
            "input_message_content": content,
        })
        return True

    def run(self):
        print("⚡ TDDownloader client running...")
        self.client.run()


class TDFileHelper:
    def __init__(self, td_client):
        self.client = td_client

    async def get_file_info(self, chat_id: int, message_id: int):
        """
        Fetch TDLib file info (file_id, file_name, file_type) using chat_id & message_id.
        Returns: dict with keys: file_id, file_name, file_type or None if not found.
        """
        try:
            msg = await self.client.invoke({
                "@type": "getMessage",
                "chat_id": chat_id,
                "message_id": message_id
            })

            if not msg or not hasattr(msg, "content"):
                return None

            return self._extract_file_data(msg.content, message_id)

        except Exception as e:
            logging.error(f"❌ Error fetching TDLib file info: {e}")
            return None

    async def get_file_info_from_link(self, link: str):
        """
        Fetch TDLib file info directly using Telegram message link.
        Example: https://t.me/c/123456789/45
        """
        try:
            info = await self.client.getMessageLinkInfo(link)
            if not info or not hasattr(info, "message"):
                logging.error(f"⚠️ Invalid or inaccessible link: {link}")
                return None

            chat_id = info.message.chat_id
            message_id = info.message.id

            msg_info = await self.client.getMessage(chat_id, message_id)
            if not hasattr(msg_info, "content"):
                logging.warning("⚠️ No content found in this message.")
                return None

            return self._extract_file_data(msg_info.content, message_id)

        except Exception as e:
            logging.error(f"❌ get_file_info_from_link error: {e}")
            return None

    def _extract_file_data(self, content, message_id: int):
        """
        Internal helper: extract file_id, name, and type from message content.
        """
        try:
            file_id = file_name = file_type = None

            if hasattr(content, "video") and content.video:
                file_id = content.video.video.id
                file_name = getattr(content.video, "file_name", "video.mp4")
                file_type = "video"
            elif hasattr(content, "document") and content.document:
                file_id = content.document.document.id
                file_name = getattr(content.document, "file_name", "document")
                file_type = "document"
            elif hasattr(content, "photo") and content.photo:
                file_id = content.photo.sizes[-1].photo.id
                file_name = f"photo_{message_id}.jpg"
                file_type = "photo"
            elif hasattr(content, "audio") and content.audio:
                file_id = content.audio.audio.id
                file_name = getattr(content.audio, "file_name", "audio.mp3")
                file_type = "audio"

            if not file_id:
                logging.warning("⚠️ No downloadable file found.")
                return None

            logging.info(f"🆔 Extracted TDLib File: {file_name} ({file_type}) → {file_id}")
            return {
                "file_id": file_id,
                "file_name": file_name,
                "file_type": file_type
            }

        except Exception as e:
            logging.error(f"❌ _extract_file_data error: {e}")
            return None
