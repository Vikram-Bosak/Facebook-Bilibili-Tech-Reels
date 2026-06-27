"""
Agent 1: Bilibili Tech Video Downloader
Searches Bilibili for tech/gadget videos using the API and downloads via
the Bilibili playurl API (no cookies, no playwright, no yt-dlp).
"""
import os
import json
import random
import re
import sys
import time
from urllib.parse import quote

from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import requests
except ImportError:
    requests = None

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────
HISTORY_FILE = "downloaded_history.txt"
QUEUE_FILE = "workspace/queue.json"
RAW_VIDEO_PATH = "workspace/raw_video.mp4"

# ── Tech keywords ────────────────────────────────────────────────────────
TECH_KEYWORDS = ["科技", "数码", "开箱", "测评", "手机", "电脑", "发明", "创新"]

# ── Bilibili API endpoints ───────────────────────────────────────────────
BILIBILI_SEARCH_ALL_URL = "https://api.bilibili.com/x/web-interface/search/all"
BILIBILI_VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
BILIBILI_PLAYURL_URL = "https://api.bilibili.com/x/player/playurl"
BILIBILI_SPI_URL = "https://api.bilibili.com/x/frontend/finger/spi"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
}


# ── Session helpers ──────────────────────────────────────────────────────
def _create_session():
    """Create a requests session with Bilibili cookies for API access."""
    if not requests:
        print("ERROR: 'requests' library not installed.")
        return None

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    # Warm cookies from homepage
    try:
        session.get("https://www.bilibili.com", timeout=10)
    except Exception:
        pass

    # Get buvid3/buvid4 from SPI endpoint
    try:
        resp_spi = session.get(BILIBILI_SPI_URL, timeout=10)
        spi = resp_spi.json()
        if spi.get("code") == 0:
            b3 = spi["data"].get("b_3", "")
            b4 = spi["data"].get("b_4", "")
            if b3:
                session.cookies.set("buvid3", b3, domain=".bilibili.com")
            if b4:
                session.cookies.set("buvid4", b4, domain=".bilibili.com")
    except Exception:
        pass

    return session


# ── History / Queue persistence ──────────────────────────────────────────
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return set(f.read().splitlines())
    return set()


def save_to_history(video_id):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{video_id}\n")


def load_queue():
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_queue(queue):
    os.makedirs(os.path.dirname(QUEUE_FILE) or ".", exist_ok=True)
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


# ── Search Bilibili ─────────────────────────────────────────────────────
def search_bilibili(session, keyword):
    """
    Search Bilibili for tech videos using the search/all API.
    Returns list of dicts with bvid, title, author, etc.
    """
    params = {"keyword": keyword}

    try:
        print(f"  Searching Bilibili for: {keyword}")
        resp = session.get(BILIBILI_SEARCH_ALL_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print(f"  API error for '{keyword}': code={data.get('code')}, msg={data.get('message')}")
            return []

        # Videos are in data.result.video
        result = data.get("data", {}).get("result", {})
        raw_videos = result.get("video", []) if isinstance(result, dict) else []

        videos = []
        for item in raw_videos:
            bvid = item.get("bvid", "")
            title = item.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
            author = item.get("author", "")
            duration = item.get("duration", "")
            play = item.get("play", 0)
            pic = item.get("pic", "")

            if bvid:
                videos.append(
                    {
                        "bvid": bvid,
                        "aid": item.get("aid", 0),
                        "title": title,
                        "author": author,
                        "duration": duration,
                        "play": play,
                        "pic": pic,
                        "source_url": f"https://www.bilibili.com/video/{bvid}",
                    }
                )

        print(f"  Found {len(videos)} videos for '{keyword}'")
        return videos

    except Exception as e:
        print(f"  Error searching Bilibili for '{keyword}': {e}")
        return []


def search_all_tech_keywords(session, keywords=None):
    """
    Search Bilibili for multiple tech keywords and return deduplicated results.
    Picks a random subset each run for variety.
    """
    if keywords is None:
        keywords = TECH_KEYWORDS

    all_videos = []
    seen_bvids = set()

    selected = random.sample(keywords, min(4, len(keywords)))
    print(f"Searching Bilibili for keywords: {selected}")

    for kw in selected:
        results = search_bilibili(session, kw)
        for video in results:
            bvid = video["bvid"]
            if bvid not in seen_bvids:
                seen_bvids.add(bvid)
                all_videos.append(video)

    print(f"Total unique tech videos found: {len(all_videos)}")
    return all_videos


# ── Queue management ─────────────────────────────────────────────────────
def add_videos_to_queue(videos):
    """Add discovered videos to the download queue, skipping duplicates and history."""
    history = load_history()
    queue = load_queue()
    queued_ids = {item["id"] for item in queue}

    new_count = 0
    for video in videos:
        vid_id = video["bvid"]
        if vid_id in history or vid_id in queued_ids:
            continue

        queue.append(
            {
                "id": vid_id,
                "title": video["title"],
                "source_url": video["source_url"],
                "author": video.get("author", ""),
                "duration": video.get("duration", ""),
                "status": "PENDING",
            }
        )
        queued_ids.add(vid_id)
        new_count += 1

    if new_count > 0:
        save_queue(queue)
        print(f"Added {new_count} new tech videos to the queue.")
    else:
        print("No new unique tech videos to add.")

    return queue


# ── Download via Bilibili playurl API ────────────────────────────────────
def _get_cid(session, bvid):
    """
    Step 1: Get CID (and other metadata) from the view API.
    https://api.bilibili.com/x/web-interface/view?bvid=BVxxx
    """
    try:
        resp = session.get(BILIBILI_VIEW_URL, params={"bvid": bvid}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print(f"  View API error for {bvid}: code={data.get('code')}, msg={data.get('message')}")
            return None

        view_data = data.get("data", {})
        cid = view_data.get("cid", 0)
        aid = view_data.get("aid", 0)
        pages = view_data.get("pages", [])

        # For multi-part videos, use the first page's cid
        if not cid and pages:
            cid = pages[0].get("cid", 0)

        if not cid:
            print(f"  No CID found for {bvid}")
            return None

        return {"cid": cid, "aid": aid, "title": view_data.get("title", "")}

    except Exception as e:
        print(f"  Error getting CID for {bvid}: {e}")
        return None


def _get_playurl(session, bvid, cid):
    """
    Step 2: Get the direct stream URL from the playurl API.
    https://api.bilibili.com/x/player/playurl?bvid=BVxxx&cid=CID&qn=16
    qn=16 is 360p — small enough for quick download, works without login.
    """
    try:
        params = {
            "bvid": bvid,
            "cid": cid,
            "qn": 16,       # 360p — requires no authentication
            "fnval": 1,      # DASH format (returns video+audio separately)
        }
        resp = session.get(BILIBILI_PLAYURL_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print(f"  Playurl API error for {bvid}: code={data.get('code')}, msg={data.get('message')}")
            return None

        playurl = data.get("data", {})

        # DASH format: separate video and audio streams
        dash = playurl.get("dash")
        if dash:
            video_streams = dash.get("video", [])
            audio_streams = dash.get("audio", [])

            if video_streams:
                # Pick the first (smallest) video stream
                video_url = video_streams[0].get("baseUrl") or video_streams[0].get("base_url", "")
                # Pick the first audio stream if available
                audio_url = ""
                if audio_streams:
                    audio_url = audio_streams[0].get("baseUrl") or audio_streams[0].get("base_url", "")

                if video_url:
                    return {"video_url": video_url, "audio_url": audio_url, "format": "dash"}

        # Durl format (combined audio+video, fallback)
        durl = playurl.get("durl", [])
        if durl:
            stream_url = durl[0].get("url", "")
            if stream_url:
                return {"video_url": stream_url, "audio_url": "", "format": "durl"}

        print(f"  No playable URL found for {bvid}")
        return None

    except Exception as e:
        print(f"  Error getting playurl for {bvid}: {e}")
        return None


def _download_stream(session, url, output_path):
    """
    Step 3: Download the video stream directly with requests.
    Streams in chunks to handle large files.
    """
    try:
        download_headers = {
            "User-Agent": DEFAULT_HEADERS["User-Agent"],
            "Referer": "https://www.bilibili.com",
        }
        resp = session.get(url, headers=download_headers, stream=True, timeout=60)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 // total
                        print(f"\r  Downloading: {pct}% ({downloaded}/{total} bytes)", end="", flush=True)

        print()  # newline after progress
        file_size = os.path.getsize(output_path)
        if file_size < 1000:
            print(f"  Downloaded file too small ({file_size} bytes) — likely failed.")
            os.remove(output_path)
            return False

        print(f"  Downloaded {file_size} bytes to {output_path}")
        return True

    except Exception as e:
        print(f"  Download error: {e}")
        return False


def _merge_video_audio(video_path, audio_path, output_path):
    """Merge separate video and audio streams using ffmpeg."""
    try:
        import ffmpeg

        video_in = ffmpeg.input(video_path)
        audio_in = ffmpeg.input(audio_path)

        out = ffmpeg.output(
            video_in,
            audio_in,
            output_path,
            vcodec="copy",
            acodec="copy",
        )
        ffmpeg.run(out, overwrite_output=True, quiet=True)

        # Remove temp files
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)

        return True
    except Exception as e:
        print(f"  FFmpeg merge error: {e}")
        # If merge fails, try renaming the video-only file as the final output
        if os.path.exists(video_path):
            os.rename(video_path, output_path)
        return True


def download_video_playurl(session, video):
    """
    Download a Bilibili video using the playurl API pattern:
    1. Get CID from /x/web-interface/view?bvid=BVxxx
    2. Get stream URL from /x/player/playurl?bvid=BVxxx&cid=CID&qn=16
    3. Download stream with requests.get()

    For DASH format (separate video+audio), uses ffmpeg to merge.
    """
    bvid = video["bvid"]
    print(f"Downloading: {video['title']} ({video['source_url']})")
    os.makedirs("workspace", exist_ok=True)

    # Step 1: Get CID
    print(f"  [1/3] Getting video info for {bvid}...")
    info = _get_cid(session, bvid)
    if not info:
        print(f"  Failed to get CID for {bvid}")
        return None

    cid = info["cid"]
    print(f"  CID: {cid}")

    # Step 2: Get playurl
    print(f"  [2/3] Getting stream URL...")
    playurl = _get_playurl(session, bvid, cid)
    if not playurl:
        print(f"  Failed to get playurl for {bvid}")
        return None

    video_url = playurl["video_url"]
    audio_url = playurl.get("audio_url", "")
    fmt = playurl["format"]

    # Step 3: Download
    print(f"  [3/3] Downloading stream ({fmt} format)...")

    if fmt == "dash" and audio_url:
        # DASH: download video and audio separately, then merge
        temp_video = "workspace/temp_video.m4s"
        temp_audio = "workspace/temp_audio.m4s"

        if not _download_stream(session, video_url, temp_video):
            return None
        if not _download_stream(session, audio_url, temp_audio):
            return None

        print("  Merging video and audio...")
        if not _merge_video_audio(temp_video, temp_audio, RAW_VIDEO_PATH):
            print("  FFmpeg merge failed.")
            return None
    else:
        # Durl: single combined stream
        if not _download_stream(session, video_url, RAW_VIDEO_PATH):
            return None

    print(f"  Video saved to {RAW_VIDEO_PATH}")
    return RAW_VIDEO_PATH


# ── Main entry point ─────────────────────────────────────────────────────
def run_downloader():
    """
    Main downloader entry point:
    1. Create authenticated session
    2. Search Bilibili for tech videos
    3. Add to queue
    4. Download first pending video using playurl API
    5. Return video_data dict expected by editor
    """
    print("Running Downloader: Searching Bilibili for tech videos...")

    session = _create_session()
    if not session:
        print("Failed to create Bilibili session.")
        return None

    # Step 1 & 2: Search and add to queue
    videos = search_all_tech_keywords(session)
    queue = add_videos_to_queue(videos)

    # Step 3: Find first pending video
    pending = [item for item in queue if item.get("status") == "PENDING"]
    if not pending:
        print("No pending videos in queue after search.")
        return None

    # Step 4: Download the first pending video using playurl API
    item = pending[0]
    print(f"Next pending video: {item['title']} ({item['source_url']})")

    local_path = download_video_playurl(session, item)
    if not local_path:
        print("Download failed. Skipping this video.")
        item["status"] = "FAILED"
        save_queue(queue)
        return None

    # Update queue entry
    item["status"] = "DOWNLOADING"
    item["local_path"] = local_path
    save_queue(queue)

    # Save to history
    save_to_history(item["id"])

    # Return data expected by editor (agent_2_editor.py)
    return item


if __name__ == "__main__":
    run_downloader()
