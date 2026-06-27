import os
import json
import urllib.parse
import requests
import re

HISTORY_FILE = 'downloaded_history.txt'
QUEUE_FILE = 'workspace/queue.json'

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return set(f.read().splitlines())
    return set()

def save_to_history(video_id):
    with open(HISTORY_FILE, 'a') as f:
        f.write(f"{video_id}\n")

def load_queue():
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_queue(queue):
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=2)

def download_video(url, output_path):
    """Download video using yt-dlp"""
    import subprocess
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        'yt-dlp',
        '-f', 'best[height<=1920]',
        '--no-playlist',
        '-o', output_path,
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True
    print(f"yt-dlp error: {result.stderr}")
    return False

def scan_bilibili_tech():
    """Scan Bilibili for tech/gadget videos using API"""
    print("Scanning Bilibili for tech/gadget videos...")
    
    history = load_history()
    queue = load_queue()
    queued_ids = {item['id'] for item in queue}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/"
    }
    
    tech_keywords = ["科技", "数码", "开箱", "测评", "评测", "新品", "手机", "电脑", " gadget", "发明", "创新"]
    new_candidates = []
    
    for kw in tech_keywords:
        try:
            url = f"https://api.bilibili.com/x/web-interface/wbi/search/all/v2?keyword={urllib.parse.quote(kw)}"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get('code') == 0:
                    result = data.get('data', {}).get('result', [])
                    video_result = None
                    if isinstance(result, list):
                        for item in result:
                            if isinstance(item, dict) and item.get('result_type') == 'video':
                                video_result = item
                                break
                    
                    if video_result:
                        data_list = video_result.get('data', [])
                        for v in data_list[:5]:
                            bvid = v.get('bvid')
                            if not bvid:
                                continue
                            if bvid in history or bvid in queued_ids:
                                continue
                            
                            title_clean = re.sub(r'<[^>]+>', '', v.get('title', ''))
                            video_url = f"https://www.bilibili.com/video/{bvid}"
                            new_candidates.append({
                                "id": bvid,
                                "title": title_clean[:120],
                                "source_url": video_url,
                                "status": "PENDING"
                            })
                            print(f"Found: {bvid} | {title_clean[:50]}")
        except Exception as e:
            print(f"Error scanning keyword '{kw}': {e}")
    
    if new_candidates:
        seen_ids = {c['id'] for c in queue}
        unique = [c for c in new_candidates if c['id'] not in seen_ids]
        if unique:
            queue.extend(unique)
            save_queue(queue)
            print(f"Added {len(unique)} videos to queue.")
    
    return queue

def run_downloader():
    print("Running Bilibili Tech Downloader...")
    queue = scan_bilibili_tech()
    
    # Download first pending video
    pending = [item for item in queue if item['status'] == 'PENDING']
    if pending:
        item = pending[0]
        output_path = f"workspace/raw_video.mp4"
        print(f"Downloading: {item['source_url']}")
        
        if download_video(item['source_url'], output_path):
            item['status'] = 'DOWNLOADED'
            item['local_path'] = output_path
            save_queue(queue)
            save_to_history(item['id'])
            return item
        else:
            print("Download failed.")
            return None
    
    print("No pending videos.")
    return None

if __name__ == "__main__":
    run_downloader()
