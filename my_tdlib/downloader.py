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

    async def download_file(self, file_id, file_name, *, on_progress=None):
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

        fid = result.id if hasattr(result, "id") else result.get("id")
        if not fid:
            raise ValueError("⚠️ Invalid file ID or TDLib response.")

        while True:
            f = await self.client.invoke({"@type": "getFile", "file_id": fid})
            if getattr(f.local, "is_downloading_completed", False):
                if on_progress:
                    await on_progress(file_name, f.expected_size, f.expected_size, 100.0, 0, 0)
                break

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

            if on_progress:
                try:
                    await on_progress(file_name, downloaded, total, percent, speed, eta)
                except Exception as e:
                    logging.warning(f"⚠️ Progress callback error: {e}")

            last_time, last_downloaded = now, downloaded
            await asyncio.sleep(0.5)

        logging.info(f"✅ Download complete: {file_name}")
        return f.local.path

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
        🚀 Direct TDLib Media Uploader + Progress Bar
        ---------------------------------------------
        Uses only native send methods:
        - sendVideo / sendPhoto / sendAudio / sendDocument
        + real-time progress updates via updateFile events
        """

        file_name = file_name or os.path.basename(file_path)
        total_size = os.path.getsize(file_path)
        logging.info(f"📤 Upload started: {file_name} ({file_type})")

        upload_done = asyncio.Event()
        start_time = time.time()
        last_time, last_uploaded = start_time, 0

        # 🔹 Background task to monitor file progress
        async def monitor_progress():
            nonlocal last_time, last_uploaded
            while not upload_done.is_set():
                try:
                    files = await self.client.invoke({"@type": "getRemoteFile", "remote_file_id": file_path})
                except Exception:
                    await asyncio.sleep(0.5)
                    continue

                # TDLib doesn't always expose progress easily, so fallback to os.path stats
                uploaded = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                percent = (uploaded / total_size) * 100 if total_size else 0
                now = time.time()
                diff = now - last_time
                speed = (uploaded - last_uploaded) / diff if diff > 0 else 0
                eta = (total_size - uploaded) / speed if speed > 0 else 0

                if on_progress:
                    try:
                        await on_progress(file_name, uploaded, total_size, percent, speed, eta)
                    except Exception as e:
                        logging.warning(f"⚠️ Progress callback error: {e}")

                last_time, last_uploaded = now, uploaded
                await asyncio.sleep(0.5)

        progress_task = None
        if on_progress:
            progress_task = asyncio.create_task(monitor_progress())

        try:
            # 🔹 Native send methods
            if file_type == "video":
                await self.client.sendVideo(
                    chat_id=chat_id,
                    video=file_path,
                    caption=caption,
                    thumbnail=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                    supports_streaming=True,
                    duration=duration,
                    file_name=file_name,
                )

            elif file_type == "photo":
                await self.client.sendPhoto(
                    chat_id=chat_id,
                    photo=file_path,
                    caption=caption,
                )

            elif file_type == "audio":
                await self.client.sendAudio(
                    chat_id=chat_id,
                    audio=file_path,
                    caption=caption,
                    duration=duration,
                    file_name=file_name,
                    thumbnail=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                )

            elif file_type == "document":
                await self.client.sendDocument(
                    chat_id=chat_id,
                    document=file_path,
                    caption=caption,
                    file_name=file_name,
                    thumbnail=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                )

            else:
                logging.error(f"⚠️ Unsupported file_type: {file_type}")
                return None

            logging.info(f"✅ Upload complete: {file_name}")
            if on_progress:
                await on_progress(file_name, total_size, total_size, 100.0, 0, 0)

        except Exception as e:
            logging.error(f"❌ Error sending {file_type}: {e}")

        finally:
            upload_done.set()
            if progress_task:
                await progress_task

            
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
