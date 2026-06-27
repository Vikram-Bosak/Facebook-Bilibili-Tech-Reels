import os
import json
import requests
from PIL import Image, ImageDraw, ImageFont
import ffmpeg

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

def generate_headline(title):
    """Generate a catchy headline using Nvidia API"""
    if not OPENAI_API_KEY:
        print("No API key found. Using title as headline.")
        return {"hook": title, "highlights": []}
    
    try:
        import openai
        client = openai.OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=OPENAI_API_KEY,
            timeout=30.0
        )
        
        prompt = f"""Analyze this Chinese tech title: '{title}'
Create a catchy, clickbait-style headline for a short video.
Rules:
1. Must create curiosity and make viewers stop scrolling
2. Keep it short (5-15 characters)
3. Use impactful words
4. Output in Chinese
5. Return JSON: {{"hook": "your headline"}}"""
        
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )
        
        raw = response.choices[0].message.content.strip()
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return {"hook": data.get("hook", title), "highlights": []}
    except Exception as e:
        print(f"Headline generation error: {e}")
    
    return {"hook": title, "highlights": []}

def download_font():
    """Download Chinese-compatible font"""
    font_path = "assets/NotoSansSC-Regular.ttf"
    os.makedirs('assets', exist_ok=True)
    if not os.path.exists(font_path):
        print("Downloading font...")
        url = "https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            with open(font_path, 'wb') as f:
                f.write(r.content)
        except Exception as e:
            print(f"Font download failed: {e}")
    return font_path

def create_overlay_image(headline_data, output_path):
    """Create 1080x1920 overlay with yellow border and text"""
    width, height = 1080, 1920
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Yellow border
    draw.rectangle([0, 0, width-1, height-1], outline=(255, 255, 0, 255), width=15)
    
    # Text
    font_path = download_font()
    font = ImageFont.truetype(font_path, 70)
    
    hook = headline_data.get("hook", "")
    if hook:
        bbox = draw.textbbox((0, 0), hook, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (width - text_w) / 2
        y = 150
        
        # Black background for text
        draw.rectangle([x-20, y-15, x+text_w+20, y+text_h+15], fill=(0, 0, 0, 255))
        draw.text((x, y), hook, font=font, fill=(255, 255, 0, 255))
    
    # "热门" at bottom
    hot_font = ImageFont.truetype(font_path, 90)
    hot_text = "科技"
    hot_bbox = draw.textbbox((0, 0), hot_text, font=hot_font)
    hot_w = hot_bbox[2] - hot_bbox[0]
    hot_h = hot_bbox[3] - hot_bbox[1]
    hot_x = (width - hot_w) / 2
    hot_y = height - 200
    draw.rectangle([hot_x-40, hot_y-20, hot_x+hot_w+40, hot_y+hot_h+30], fill=(0, 0, 0, 255))
    draw.text((hot_x, hot_y), hot_text, font=hot_font, fill=(255, 255, 0, 255))
    
    img.save(output_path)
    print(f"Overlay saved: {output_path}")

def edit_video(input_path, overlay_path, output_path):
    """Composite video with overlay"""
    print("Compositing video...")
    try:
        base = ffmpeg.input('color=c=black:s=1080x1920', f='lavfi')
        vid = ffmpeg.input(input_path)
        overlay = ffmpeg.input(overlay_path)
        
        scaled = vid.video.filter('scale', 1080, 1920, force_original_aspect_ratio='increase').filter('crop', 1080, 1920)
        on_base = ffmpeg.overlay(base, scaled, x=0, y=0, shortest=1)
        final = ffmpeg.overlay(on_base, overlay, x=0, y=0)
        
        out = ffmpeg.output(final, vid.audio, output_path, vcodec='libx264', acodec='aac', crf=28, preset='fast')
        ffmpeg.run(out, overwrite_output=True, quiet=True)
        
        # Get duration
        probe = ffmpeg.probe(output_path)
        duration = float(probe['format']['duration'])
        print(f"Final video: {duration:.2f}s")
        return True
    except Exception as e:
        print(f"Edit error: {e}")
        return False

def process_video(video_data):
    """Main edit pipeline"""
    print("Starting Video Editor...")
    
    raw_path = video_data.get('local_path', 'workspace/raw_video.mp4')
    title = video_data.get('title', 'Unknown')
    overlay_path = 'workspace/overlay.png'
    edited_path = f"workspace/edited_{video_data.get('id', 'video')}.mp4"
    
    if not os.path.exists(raw_path):
        print(f"Raw video not found: {raw_path}")
        video_data['editing_status'] = 'Failed'
        return video_data
    
    # Generate headline
    headline = generate_headline(title)
    print(f"Headline: {headline.get('hook', '')}")
    
    # Create overlay
    create_overlay_image(headline, overlay_path)
    
    # Edit video
    if edit_video(raw_path, overlay_path, edited_path):
        video_data['editing_status'] = 'Success'
        video_data['edited_path'] = edited_path
        video_data['seo_title'] = headline.get('hook', '')
        
        # Cleanup
        if os.path.exists(raw_path):
            os.remove(raw_path)
        if os.path.exists(overlay_path):
            os.remove(overlay_path)
    else:
        video_data['editing_status'] = 'Failed'
    
    return video_data

if __name__ == "__main__":
    pass
