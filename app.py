from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import json
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
CORS(app)

def extract_youtube_video_id(url):
    """YouTube URL se video ID nikaalein"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([\w-]+)',
        r'(?:youtu\.be\/)([\w-]+)',
        r'(?:youtube\.com\/embed\/)([\w-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_youtube_video_direct(video_id):
    """YouTube video ko direct download karein (without any API)"""
    try:
        # YouTube player page se data nikaalein
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        
        # YouTube ke player response mein video URLs hote hain
        # "ytInitialPlayerResponse" JSON nikaalein
        match = re.search(r'var ytInitialPlayerResponse = ({.*?});', response.text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            # Streaming data mein se best quality video URL nikaalein
            streaming = data.get('streamingData', {})
            formats = streaming.get('formats', []) + streaming.get('adaptiveFormats', [])
            
            # Sab se high quality wala format choose karein
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
        
        # Agar JSON nahi mila toh alternate method
        # YouTube ke video page mein "playabilityStatus" check karein
        playability_match = re.search(r'"playabilityStatus":\s*({.*?})', response.text)
        if playability_match:
            status = json.loads(playability_match.group(1))
            if status.get('status') == 'UNPLAYABLE':
                print("Video unavailable or age-restricted")
                return None
        
        return None
    except Exception as e:
        print(f"YouTube direct error: {e}")
        return None

def fallback_saveform(url):
    """Saveform.net (for Instagram/TikTok)"""
    try:
        session = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "alive", "message": "Use POST /fetch with { 'url': '...' }"})

@app.route("/fetch", methods=["POST"])
def fetch():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "URL nahi mila"}), 400
    
    user_url = data["url"]
    
    # 1. Check if it's a YouTube URL
    video_id = extract_youtube_video_id(user_url)
    if video_id:
        video_url = get_youtube_video_direct(video_id)
        if video_url:
            return jsonify({"success": True, "downloadUrl": video_url, "method": "YouTube Direct"})
    
    # 2. Agar YouTube nahi hai toh saveform.net try karein (Instagram, TikTok, Facebook)
    video_url = fallback_saveform(user_url)
    if video_url:
        return jsonify({"success": True, "downloadUrl": video_url, "method": "saveform.net"})
    
    return jsonify({"success": False, "error": "Video nahi mili. Link check karein."}), 404

if __name__ == "__main__":
    app.run(debug=True)
