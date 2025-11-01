# my_tdlib/downloader.py  🚀 FULL ADVANCED

import asyncio
import time
import os
import logging
import math
import subprocess
from .config import get_client


class TDDownloader:
    def __init__(self, api_id, api_hash, token, encryption_key="1234_ast$"):
        self.client = get_client(api_id, api_hash, token, encryption_key)

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
        Forces real upload (no cache reuse).
        """
        file_name = file_name or os.path.basename(file_path)
        total_size = os.path.getsize(file_path)
        logging.info(f"📤 Upload started: {file_name} ({total_size/1024/1024:.2f} MB)")

        upload_done = asyncio.Event()
        start_time = time.time()
        last_time, last_uploaded = start_time, 0

        # 🔹 Local progress monitor
        async def monitor_progress():
            nonlocal last_time, last_uploaded
            while not upload_done.is_set():
                try:
                    uploaded = os.path.getsize(file_path)
                    percent = (uploaded / total_size) * 100 if total_size else 0
                    now = time.time()
                    diff = now - last_time
                    speed = (uploaded - last_uploaded) / diff if diff > 0 else 0
                    eta = (total_size - uploaded) / speed if speed > 0 else 0
                    if on_progress:
                        await on_progress(file_name, uploaded, total_size, percent, speed, eta)
                    last_time, last_uploaded = now, uploaded
                    await asyncio.sleep(1)
                except Exception:
                    await asyncio.sleep(1)

        progress_task = asyncio.create_task(monitor_progress()) if on_progress else None

        try:
            # ✅ Force TDLib to treat this as new file
            if os.path.exists(file_path):
                temp_copy = f"/tmp/{int(time.time())}_{os.path.basename(file_path)}"
                os.system(f"cp '{file_path}' '{temp_copy}'")
                try:
                    with open(temp_copy, "ab") as f:
                        f.write(b" ")  # add dummy byte
                    logging.info("🧩 Appended dummy byte to break TDLib hash cache")
                except Exception as e:
                    logging.warning(f"⚠️ Could not append dummy byte: {e}")
                file_path = temp_copy
                logging.info(f"🧠 Forcing fresh path upload: {file_path}")

            input_file = {"@type": "inputFileLocal", "path": file_path}
            logging.info(f"🧾 TDLib input file prepared: {input_file}")

            if file_type == "video":
                result = await self.client.sendVideo(chat_id=chat_id, video=input_file, caption=caption, duration=int(duration or 0))
            elif file_type == "photo":
                result = await self.client.sendPhoto(chat_id=chat_id, photo=input_file, caption=caption)
            elif file_type == "audio":
                result = await self.client.sendAudio(chat_id=chat_id, audio=input_file, caption=caption, duration=duration)
            elif file_type == "document":
                result = await self.client.sendDocument(chat_id=chat_id, document=input_file, caption=caption)
            else:
                logging.error(f"⚠️ Unsupported file_type: {file_type}")
                return None

            logging.info(f"✅ Upload complete: {file_name}")
            if on_progress:
                await on_progress(file_name, total_size, total_size, 100.0, 0, 0)
            return result

        except Exception as e:
            logging.error(f"❌ Error sending {file_type}: {e}")
            return None

        finally:
            upload_done.set()
            if progress_task:
                await progress_task
            try:
                if file_path.startswith("/tmp/") and os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"🧹 Deleted temp file after upload: {file_path}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to delete temp file: {e}")




            
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
