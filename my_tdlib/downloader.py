import asyncio
import time
from .utils import format_size, format_time
from .config import get_client


class TDDownloader:
    def __init__(self, api_id, api_hash, token, encryption_key="1234_ast$"):
        self.client = get_client(api_id, api_hash, token, encryption_key)
        self.client.start()

    async def _progress(self, msg, name, done, total, speed, upload=False):
        if total == 0:
            return
        p = (done / total) * 100
        bar = "█" * int(p / 5) + "░" * (20 - int(p / 5))
        eta = (total - done) / speed if speed > 0 else 0
        act = "⬆️ Uploading" if upload else "⬇️ Downloading"

        text = (
            f"{act}: **{name}**\n\n"
            f"`{bar}` {p:.1f}%\n"
            f"📦 {format_size(done)} / {format_size(total)}\n"
            f"⚡ {format_size(speed)}/s\n"
            f"⏱️ {format_time(eta)}"
        )
        try:
            await msg.edit_text(text, parse_mode="markdown")
        except:
            pass

    async def download_message_file(self, message, td_message):
        """
        message = pyrogram message (for UI updates)
        td_message = TDLib message (with .content.document.document.id)
        """
        file_obj = td_message.content.document.document
        fid = file_obj.id
        name = getattr(td_message.content.document, "file_name", "file.bin")

        status = await message.reply_text("⬇️ Starting TDLib download...")
        start = time.time()
        last_time, last_size = start, 0

        result = await self.client.invoke({
            "@type": "downloadFile",
            "file_id": fid,
            "priority": 32,
            "synchronous": False,
        })
        file_id = result.id if hasattr(result, "id") else result.get("id")

        while True:
            f = await self.client.invoke({"@type": "getFile", "file_id": file_id})
            if getattr(f.local, "is_downloading_completed", False):
                await self._progress(status, name, f.expected_size, f.expected_size, 0)
                break

            now = time.time()
            downloaded = getattr(f.local, "downloaded_size", 0)
            total = getattr(f, "expected_size", 0)
            speed = (downloaded - last_size) / (now - last_time) if now > last_time else 0
            await self._progress(status, name, downloaded, total, speed)
            last_time, last_size = now, downloaded
            await asyncio.sleep(0.5)

        await status.edit_text("✅ Download complete!")
        return f.local.path

    async def upload_file(self, chat_id, file_path, caption="", file_type="document"):
        types_map = {
            "document": "inputMessageDocument",
            "photo": "inputMessagePhoto",
            "video": "inputMessageVideo",
            "audio": "inputMessageAudio"
        }
        input_type = types_map.get(file_type, "inputMessageDocument")

        await self.client.invoke({
            "@type": "sendMessage",
            "chat_id": chat_id,
            "input_message_content": {
                "@type": input_type,
                file_type: {"@type": "inputFileLocal", "path": file_path},
                "caption": {"@type": "formattedText", "text": caption},
            }
        })
        return True
