import os
import json
import requests
import urllib.parse
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

FEED_FILE = 'workspace/reels_feed.xml'

def fetch_bilibili_videos(keyword):
    """Fetch tech videos from Bilibili API"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/"
    }
    videos = []
    try:
        url = f"https://api.bilibili.com/x/web-interface/wbi/search/all/v2?keyword={urllib.parse.quote(keyword)}"
        r = requests.get(url, headers=headers, timeout=15)
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
                        if bvid:
                            title_clean = re.sub(r'<[^>]+>', '', v.get('title', ''))
                            videos.append({
                                'id': bvid,
                                'title': title_clean,
                                'link': f"https://www.bilibili.com/video/{bvid}",
                                'description': f"Bilibili tech video: {keyword}"
                            })
    except Exception as e:
        print(f"Error fetching '{keyword}': {e}")
    return videos

def generate_rss():
    """Generate RSS feed from Bilibili tech videos"""
    print("Generating RSS feed for tech videos...")
    os.makedirs(os.path.dirname(FEED_FILE), exist_ok=True)
    
    keywords = ["科技", "数码", "开箱", "测评", "手机", "电脑", "发明", "创新"]
    
    collected_items = []
    for kw in keywords:
        print(f"Searching: {kw}")
        collected_items.extend(fetch_bilibili_videos(kw))
    
    unique_items = []
    seen_ids = set()
    for item in collected_items:
        if item['id'] not in seen_ids:
            unique_items.append(item)
            seen_ids.add(item['id'])
    
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    title = ET.SubElement(channel, "title")
    title.text = "Chinese Tech Videos RSS Feed"
    
    link = ET.SubElement(channel, "link")
    link.text = "http://localhost/reels_feed.xml"
    
    desc = ET.SubElement(channel, "description")
    desc.text = "Chinese tech videos from Bilibili"
    
    for item in unique_items:
        item_node = ET.SubElement(channel, "item")
        
        i_title = ET.SubElement(item_node, "title")
        i_title.text = item['title']
        
        i_link = ET.SubElement(item_node, "link")
        i_link.text = item['link']
        
        i_guid = ET.SubElement(item_node, "guid")
        i_guid.text = item['id']
        
        i_desc = ET.SubElement(item_node, "description")
        i_desc.text = item['description']
    
    xml_str = ET.tostring(rss, encoding='utf-8')
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")
    
    with open(FEED_FILE, 'wb') as f:
        f.write(pretty_xml)
    
    print(f"RSS feed generated: {len(unique_items)} videos")
    return FEED_FILE

if __name__ == "__main__":
    generate_rss()
