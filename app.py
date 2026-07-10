from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import json
import os

app = Flask(__name__)
CORS(app)

# ---------- YOUTUBE DIRECT METHOD (Scraping) ----------
def extract_youtube_video_id(url):
    """YouTube URL se video ID nikaalein"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([\w-]+)',
        r'(?:youtu\.be\/)([\w-]+)',
        r'(?:youtube\.com\/embed\/)([\w-]+)',
        r'(?:youtube\.com\/shorts\/)([\w-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_youtube_video_direct(video_id):
    """YouTube video direct download (without API)"""
    try:
        # YouTube oEmbed API (alternative method)
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(oembed_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Agar video exist karti hai toh player page se nikaalein
            player_url = f"https://www.youtube.com/watch?v={video_id}"
            player_resp = requests.get(player_url, headers=headers, timeout=15)
            
            # ytInitialPlayerResponse JSON nikaalein
            match = re.search(r'var ytInitialPlayerResponse = ({.*?});', player_resp.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                streaming = data.get('streamingData', {})
                formats = streaming.get('formats', []) + streaming.get('adaptiveFormats', [])
                
                # Sab se high quality wala video URL
                best_url = None
                best_quality = 0
                for fmt in formats:
                    if 'url' in fmt and fmt.get('qualityLabel'):
                        quality = int(fmt['qualityLabel'].replace('p', '')) if fmt['qualityLabel'].replace('p', '').isdigit() else 0
                        if quality > best_quality:
                            best_quality = quality
                            best_url = fmt['url']
                
                if best_url:
                    return best_url
        
        # Agar oEmbed fail ho toh alternate method (player page se)
        player_url = f"https://www.youtube.com/watch?v={video_id}"
        player_resp = requests.get(player_url, headers=headers, timeout=15)
        
        # "playabilityStatus" check karein
        status_match = re.search(r'"playabilityStatus":\s*({.*?})', player_resp.text)
        if status_match:
            status = json.loads(status_match.group(1))
            if status.get('status') == 'UNPLAYABLE':
                print("Video unavailable or age-restricted")
                return None
        
        # Format URLs nikaalein
        format_match = re.search(r'"url":"(https?://[^"]+)"', player_resp.text)
        if format_match:
            return format_match.group(1)
        
        return None
    except Exception as e:
        print(f"YouTube error: {e}")
        return None

# ---------- SAVEFORM.NET (Instagram, TikTok, Facebook) ----------
def scrape_saveform(url):
    try:
        session = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        # Homepage load
        home = session.get("https://saveform.net/", headers=headers, timeout=10)
        soup = BeautifulSoup(home.text, "html.parser")
        
        # CSRF token nikaalein
        token = None
        for inp in soup.find_all("input"):
            name = inp.get("name", "")
            if "token" in name or "csrf" in name:
                token = inp.get("value")
                break
        
        data = {"url": url}
        if token:
            data["_token"] = token
        
        # POST request bhejein
        response = session.post("https://saveform.net/", data=data, headers=headers, timeout=15)
        
        # Download link nikaalein
        soup2 = BeautifulSoup(response.text, "html.parser")
        dl_link = soup2.find("a", {"id": "download-btn"}) or soup2.find("a", class_="download")
        if dl_link and dl_link.get("href"):
            return dl_link["href"]
        
        mp4_match = re.search(r'https?://[^\s"\']+\.mp4', response.text)
        if mp4_match:
            return mp4_match.group(0)
        return None
    except Exception as e:
        print(f"Saveform error: {e}")
        return None

# ---------- MAIN ENDPOINT ----------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "alive", "message": "Use POST /fetch with { 'url': '...' }"})

@app.route("/fetch", methods=["POST"])
def fetch():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "URL nahi mila"}), 400
    
    user_url = data["url"]
    video_id = extract_youtube_video_id(user_url)
    
    # 1. YouTube
    if video_id:
        video_url = get_youtube_video_direct(video_id)
        if video_url:
            return jsonify({"success": True, "downloadUrl": video_url, "method": "YouTube Direct"})
        else:
            # Agar YouTube fail ho toh Instagram/TikTok ke liye try karein
            pass
    
    # 2. Saveform.net (Instagram, TikTok, Facebook)
    video_url = scrape_saveform(user_url)
    if video_url:
        return jsonify({"success": True, "downloadUrl": video_url, "method": "saveform.net"})
    
    return jsonify({"success": False, "error": "Video nahi mili. Link check karein."}), 404

# ---------- FOR LOCAL TESTING ----------
if __name__ == "__main__":
    app.run(debug=True)
