import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agent_1_downloader import run_downloader
from src.agent_2_editor import process_video

def run_single_sequence():
    print("\n--- STARTING BILIBILI TECH PIPELINE ---")
    
    # 1. Download
    print("\n[Step 1] Downloading video from Bilibili...")
    video_data = run_downloader()
    if not video_data:
        print("No video found.")
        return False
    
    task_id = video_data['id']
    print(f"Downloaded Video: {task_id}")
    print(f"Source: {video_data.get('source_url', 'N/A')}")
    
    # 2. Edit
    print(f"\n[Step 2] Editing Video {task_id}...")
    try:
        video_data = process_video(video_data)
        if video_data.get('editing_status') == 'Success':
            print(f"✅ Editing Complete: {video_data.get('edited_path')}")
        else:
            print("❌ Editing Failed")
            return False
    except Exception as e:
        print(f"❌ Editing failed: {e}")
        return False
    
    print("\n--- PIPELINE COMPLETE ---")
    print(f"Edited video saved to: {video_data.get('edited_path')}")
    return True

if __name__ == "__main__":
    run_single_sequence()
