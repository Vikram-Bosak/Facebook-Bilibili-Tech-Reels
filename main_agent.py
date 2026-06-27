import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.rss_generator import generate_rss
from src.agent_1_downloader import run_downloader
from src.agent_2_editor import process_video

def run_single_sequence():
    print("\n--- STARTING BILIBILI TECH PIPELINE ---")
    
    print("\n[Step 0] Generating RSS feed...")
    try:
        generate_rss()
    except Exception as e:
        print(f"RSS generation failed: {e}")
    
    print("\n[Step 1] Downloading video...")
    video_data = run_downloader()
    if not video_data:
        print("No video found.")
        return False
    
    task_id = video_data['id']
    print(f"Downloaded: {task_id}")
    
    print(f"\n[Step 2] Editing Video {task_id}...")
    try:
        video_data = process_video(video_data)
        if video_data.get('editing_status') == 'Success':
            print(f"✅ Edit Complete: {video_data.get('edited_path')}")
        else:
            print("❌ Edit Failed")
            return False
    except Exception as e:
        print(f"❌ Edit failed: {e}")
        return False
    
    print("\n--- PIPELINE COMPLETE ---")
    return True

if __name__ == "__main__":
    run_single_sequence()
