import asyncio
import os
import re
import json
import random
import logging
import aiohttp
from typing import Union
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
import yt_dlp

import config
from VenomMusic import app
from VenomMusic.misc import _boot_
from VenomMusic.utils.database import is_on_off
from VenomMusic.utils.formatters import time_to_seconds

# ========================================================
# သင်ဝယ်ထားသော API configuration ကို ဤနေရာတွင် ထည့်ပါ
# ========================================================
MY_PAID_API_URL = "https://console.nexgenbots.xyz"  # သင်ဝယ်ထားတဲ့ API URL ကို ပြောင်းထည့်ပါ
MY_PAID_API_KEY = "30DxNexGenBots4688e6"                 # သင်ဝယ်ထားတဲ့ API KEY ကို ပြောင်းထည့်ပါ

def cookie_txt_file():
    """cookies folder ထဲက cookies.txt ဖိုင်လမ်းကြောင်းကို လုံးဝသေချာအောင် ရှာပေးသည်"""
    try:
        # လက်ရှိ Youtube.py ရှိတဲ့နေရာကနေ နောက်ပြန်တွက်ပြီး cookies.txt ကို ရှာခြင်း
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # သင့် Bot ရဲ့ root directory ကို သွားခြင်း
        root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
        cookie_file = os.path.join(root_dir, "cookies", "cookies.txt")
        
        if os.path.exists(cookie_file):
            print(f"[Cookie System] Found cookie file at: {cookie_file}")
            return cookie_file
            
        # အကယ်၍ အပေါ်ကလမ်းကြောင်း အဆင်မပြေပါက လက်ရှိ working directory ကနေ ထပ်ရှာခြင်း
        fallback_file = os.path.join(os.getcwd(), "cookies", "cookies.txt")
        if os.path.exists(fallback_file):
            print(f"[Cookie System] Found cookie file at fallback: {fallback_file}")
            return fallback_file
            
        print("[Cookie System] CRITICAL: cookies.txt file NOT FOUND anywhere!")
        return None
    except Exception as e:
        print(f"[Cookie System] Error reading cookies directory: {e}")
        return None

async def search_song_api(query: str):
    """Search for a song using API"""
    try:
        search_url = f"https://console.nexgenbots.xyz/search?q={query}"
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        return data[0]
        return None
    except Exception as e:
        print(f"Error searching with API: {e}")
        return None

async def download_song_paid_api(video_id: str):
    """သင်ဝယ်ထားသော API သုံးပြီး ဒေါင်းလုဒ်ဆွဲခြင်း"""
    try:
        # ဝယ်ထားသော API ၏ endpoint ပုံစံအတိုင်း လိုအပ်က ပြင်နိုင်သည်
        download_url = f"{MY_PAID_API_URL}/api/yt/download?id={video_id}&key={MY_PAID_API_KEY}"
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success" or "links" in data:
                        links = data.get("links", {})
                        audio_link = links.get("mp3", {}).get("url") or data.get("url")
                        return audio_link
        return None
    except Exception as e:
        print(f"Error downloading with paid API: {e}")
        return None

async def download_song(link: str):
    """သီချင်းဒေါင်းလုဒ်လုပ်ရန် အဓိက Function (Paid API -> cookies.txt Fallback)"""
    if "v=" in link:
        video_id = link.split('v=')[-1].split('&')[0]
    elif "youtu.be/" in link:
        video_id = link.split('youtu.be/')[-1].split('?')[0]
    else:
        video_id = link

    download_folder = "downloads"
    os.makedirs(download_folder, exist_ok=True)

    for ext in ["mp3", "m4a", "webm", "mp4"]:
        file_path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(file_path):
            return file_path

    # ၁။ သင်ဝယ်ထားတဲ့ Paid API ဖြင့် အရင်ဆုံး ကြိုးစားဒေါင်းယူမည်
    try:
        print(f"[Paid API] Trying to download video_id: {video_id}")
        download_url = await download_song_paid_api(video_id)
        if download_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, timeout=30) as file_response:
                    if file_response.status == 200:
                        file_path = os.path.join(download_folder, f"{video_id}.mp3")
                        with open(file_path, 'wb') as f:
                            while True:
                                chunk = await file_response.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                        print("[Paid API] Download Successful.")
                        return file_path
    except Exception as e:
        print(f"[Paid API] Failed, falling back to cookies.txt/yt-dlp: {e}")

    # ၂။ Paid API အလုပ်မလုပ်ပါက သို့မဟုတ် ကုန်သွားပါက cookies.txt ကိုသုံးပြီး Local yt-dlp ဖြင့် ဒေါင်းမည်
    print("[Local] Paid API failed. Falling back to yt-dlp with cookies.txt file...")
    loop = asyncio.get_running_loop()
    
    def local_audio_dl():
        cookie_path = cookie_txt_file()
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": f"{download_folder}/%(id)s.%(ext)s",
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
        }
        if cookie_path:
            ydl_opts["cookiefile"] = cookie_path
            print(f"[yt-dlp] Passing cookie file to yt-dlp: {cookie_path}")
        else:
            print("[yt-dlp] WARNING: Running yt-dlp WITHOUT cookies because file was not found!")
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            return os.path.join(download_folder, f"{info['id']}.{info['ext']}")

    try:
        return await loop.run_in_executor(None, local_audio_dl)
    except Exception as e:
        print(f"[yt-dlp] Local download failed too: {e}")
        return None

async def check_file_size(link):
    async def get_format_info(link):
        cmd = ["yt-dlp", "-J", link]
        cookie_path = cookie_txt_file()
        if cookie_path:
            cmd.extend(["--cookies", cookie_path])
            
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return None
        return json.loads(stdout.decode())

    info = await get_format_info(link)
    if info is None:
        return None
    formats = info.get('formats', [])
    total_size = 0
    for f in formats:
        if 'filesize' in f:
            total_size += f['filesize']
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset is None:
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        if "youtube.com/watch?v=" in link:
            video_id = link.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in link:
            video_id = link.split("youtu.be/")[-1].split("?")[0]
        else:
            video_id = link

        try:
            info_url = f"{MY_PAID_API_URL}/info/{video_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(info_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "success":
                            info = data.get("data", {})
                            title = info.get("title", "")
                            duration_min = info.get("duration", "0:00")
                            thumbnail = info.get("thumbnail", "")
                            duration_sec = 0 if str(duration_min) == "None" else int(time_to_seconds(duration_min))
                            return title, duration_min, duration_sec, thumbnail, video_id
        except Exception:
            pass
        
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = 0 if str(duration_min) == "None" else int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        title, _, _, _, _ = await self.details(link, videoid)
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        _, duration_min, _, _, _ = await self.details(link, videoid)
        return duration_min

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        _, _, _, thumbnail, _ = await self.details(link, videoid)
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        cookie_path = cookie_txt_file()
        cmd = ["yt-dlp", "-g", "-f", "best[height<=?720][width<=?1280]", link]
        if cookie_path:
            cmd.insert(1, cookie_path)
            cmd.insert(1, "--cookies")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_path = cookie_txt_file()
        cookie_str = f"--cookies {cookie_path}" if cookie_path else ""
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist {cookie_str} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            return [key for key in result if key != ""]
        except Exception:
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        title, duration_min, _, thumbnail, vidid = await self.details(link, videoid)
        track_details = {
            "title": title,
            "link": f"https://www.youtube.com/watch?v={vidid}",
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True}
        cookie_path = cookie_txt_file()
        if cookie_path:
            ytdl_opts["cookiefile"] = cookie_path
            
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                if not "dash" in str(format.get("format", "")).lower():
                    try:
                        formats_available.append({
                            "format": format["format"],
                            "filesize": format.get("filesize", 0),
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format.get("format_note", ""),
                            "yturl": link,
                        })
                    except KeyError:
                        continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            cp = cookie_txt_file()
            if cp: ydl_opts["cookiefile"] = cp
            x = yt_dlp.YoutubeDL(ydl_opts)
            info = x.extract_info(link, download=True)
            return os.path.join("downloads", f"{info['id']}.{info['ext']}")

        def video_dl():
            ydl_opts = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            cp = cookie_txt_file()
            if cp: ydl_opts["cookiefile"] = cp
            x = yt_dlp.YoutubeDL(ydl_opts)
            info = x.extract_info(link, download=True)
            return os.path.join("downloads", f"{info['id']}.{info['ext']}")

        if video:
            downloaded_file = await download_song(link)
            if not downloaded_file:
                downloaded_file = await loop.run_in_executor(None, video_dl)
            return downloaded_file, True
        else:
            downloaded_file = await download_song(link)
            if not downloaded_file:
                downloaded_file = await loop.run_in_executor(None, audio_dl)
            return downloaded_file, True
