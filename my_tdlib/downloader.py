# my_tdlib/downloader.py  🚀 FULL ADVANCED

import asyncio
import time
import os
import logging
import math
import subprocess
from .config import get_client
from pytdbot import types

class TDDownloader:
    def __init__(self, api_id, api_hash, token, encryption_key="1234_ast$"):
        self.client = get_client(api_id, api_hash, token, encryption_key)
        self.upload_progress = {}


        # Register handler correctly
        self.client.add_handler(self._on_update_file, types.UpdateFile)

    async def _on_update_file(self, update, *args):
        if update.get("@type") == "updateFile":
            file_info = update["file"]
            local = file_info.get("local", {})
            if "downloaded_size" in local and "size" in local and local["size"] > 0:
                downloaded = local["downloaded_size"]
                total = local["size"]
                percent = (downloaded / total) * 100
                print(f"📤 Upload progress: {percent:.2f}% ({downloaded}/{total} bytes)")

    async def download_file(self, link, file_name, *, on_progress=None):
        """
        Download a file from message link using TDLib (pytdbot)
        Supports progress callback.
        """
        try:
            # 🔹 Step 1: Get message info from the link
            info = await self.client.getMessageLinkInfo(link)
            if not info:
                logging.warning("⚠️ Invalid or inaccessible link.")
                return None

            chat_id = info.chat_id
            message_id = info.message.id
            logging.info(f"🔗 Getting message from chat {chat_id}, msg_id {message_id}")

            # 🔹 Step 2: Fetch full message
            public_msg = await self.client.getMessage(chat_id, message_id)
            if not public_msg:
                logging.warning("⚠️ Could not retrieve message.")
                return None

            # 🔹 Step 3: Detect content type
            content = public_msg.content
            if hasattr(content, "video"):
                media = content.video.video
            elif hasattr(content, "photo"):
                media = content.photo.sizes[-1].photo
            elif hasattr(content, "document"):
                media = content.document.document
            else:
                raise ValueError("⚠️ Unsupported media type.")

            start_time = time.time()
            last_time, last_downloaded = start_time, 0

            # 🔹 Step 4: Define progress handler
            async def progress_worker():
                nonlocal last_time, last_downloaded
                while True:
                    f = await self.client.getFile(media.id)
                    downloaded = getattr(f.local, "downloaded_size", 0)
                    total = getattr(f, "expected_size", 0) or 1
                    percent = (downloaded / total) * 100
                    now = time.time()
                    diff = now - last_time
                    speed = (downloaded - last_downloaded) / diff if diff > 0 else 0
                    eta = (total - downloaded) / speed if speed > 0 else 0

                    if on_progress:
                        try:
                            await on_progress(file_name, downloaded, total, percent, speed, eta)
                        except Exception as e:
                            logging.warning(f"⚠️ Progress callback error: {e}")

                    last_time, last_downloaded = now, downloaded

                    if getattr(f.local, "is_downloading_completed", False):
                        break
                    await asyncio.sleep(0.5)

            # 🔹 Step 5: Start download
            logging.info(f"⬇️ Starting TDLib download: {file_name}")
            progress_task = asyncio.create_task(progress_worker())
            result = await media.download(priority=1, synchronous=True)
            await progress_task

            path = getattr(result.local, "path", None)
            logging.info(f"✅ Download complete: {path}")
            return path

        except Exception as e:
            logging.error(f"❌ TDLib download failed: {e}", exc_info=True)
            return None

    async def upload_file(
        self,
        chat_id,
        file_path,
        caption="",
        file_type="document",
        *,
        file_name=None,
        thumb_path=None,
        duration=None,
        on_progress=None
    ):
        """
        📤 Uploads file to Telegram using native TDLib methods.
        Tracks real-time progress through TDLib updateFile event.
        """
        file_name = file_name or os.path.basename(file_path)
        total_size = os.path.getsize(file_path)
        logging.info(f"📤 Upload started: {file_name} ({total_size/1024/1024:.2f} MB)")

        # force TDLib re-upload
        if os.path.exists(file_path):
            temp_copy = f"/tmp/{int(time.time())}_{os.path.basename(file_path)}"
            os.system(f"cp '{file_path}' '{temp_copy}'")
            try:
                with open(temp_copy, "ab") as f:
                    f.write(b" ")
                logging.info("🧩 Appended dummy byte to break TDLib hash cache")
            except Exception as e:
                logging.warning(f"⚠️ Could not append dummy byte: {e}")
            file_path = temp_copy
            logging.info(f"🧠 Forcing fresh path upload: {file_path}")

        # register upload session
        upload_done = asyncio.Event()
        self._upload_sessions[id(file_path)] = {
            "name": file_name,
            "total": total_size,
            "done": upload_done,
            "last_time": time.time(),
            "last_uploaded": 0,
        }

        input_file = {"@type": "inputFileLocal", "path": file_path}
        logging.info(f"🧾 TDLib input file prepared: {input_file}")

        # choose TDLib method
        try:
            if file_type == "video":
                result = await self.client.sendVideo(
                    chat_id=chat_id, video=input_file, caption=caption, duration=int(duration or 0)
                )
            elif file_type == "photo":
                result = await self.client.sendPhoto(chat_id=chat_id, photo=input_file, caption=caption)
            elif file_type == "audio":
                result = await self.client.sendAudio(chat_id=chat_id, audio=input_file, caption=caption, duration=duration)
            elif file_type == "document":
                result = await self.client.sendDocument(chat_id=chat_id, document=input_file, caption=caption)
            else:
                logging.error(f"⚠️ Unsupported file_type: {file_type}")
                return None

            # wait until progress listener marks done
            await upload_done.wait()
            logging.info(f"✅ Upload complete: {file_name}")
            return result

        except Exception as e:
            logging.error(f"❌ Error sending {file_type}: {e}")
            return None

        finally:
            if file_path.startswith("/tmp/") and os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"🧹 Deleted temp file after upload: {file_path}")
            self._upload_sessions.pop(id(file_path), None)

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
