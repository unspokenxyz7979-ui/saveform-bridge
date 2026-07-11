from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import json
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

# ============================================
# YOUTUBE DIRECT (Scraping - No yt-dlp)
# ============================================
def extract_youtube_id(url):
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([\w-]+)',
        r'(?:youtu\.be\/)([\w-]+)',
        r'(?:youtube\.com\/shorts\/)([\w-]+)',
        r'(?:youtube\.com\/embed\/)([\w-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_youtube_video(video_id):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        player_url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(player_url, headers=headers, timeout=15)
        
        # Method 1: ytInitialPlayerResponse
        match = re.search(r'var ytInitialPlayerResponse = ({.*?});', response.text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            streaming = data.get('streamingData', {})
            formats = streaming.get('formats', []) + streaming.get('adaptiveFormats', [])
            
            best_url = None
            best_quality = 0
            for fmt in formats:
                if 'url' in fmt:
                    quality = 0
                    if fmt.get('qualityLabel'):
                        q_str = fmt['qualityLabel'].replace('p', '').strip()
                        if q_str.isdigit():
                            quality = int(q_str)
                    if quality > best_quality:
                        best_quality = quality
                        best_url = fmt['url']
            if best_url:
                return best_url
        
        # Method 2: Direct googlevideo URL
        url_pattern = r'https?://[^"]+\.googlevideo\.com/[^"]+'
        matches = re.findall(url_pattern, response.text)
        if matches:
            return max(matches, key=len)
        
        return None
    except Exception as e:
        print(f"YouTube error: {e}")
        return None

# ============================================
# SAVEFORM.NET (Instagram, TikTok, Facebook)
# ============================================
def scrape_saveform(url):
    try:
        session = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        home = session.get("https://saveform.net/", headers=headers, timeout=10)
        soup = BeautifulSoup(home.text, "html.parser")
        
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
        soup2 = BeautifulSoup(response.text, "html.parser")
        
        dl_link = soup2.find("a", {"id": "download-btn"}) or soup2.find("a", class_="download")
        if dl_link and dl_link.get("href"):
            return dl_link["href"]
        
        mp4_match = re.search(r'https?://[^\s"\']+\.mp4', response.text)
        if mp4_match:
            return mp4_match.group(0)
        return None
    except Exception as e:
        print(f"saveform error: {e}")
        return None

# ============================================
# FALLBACK: VEVEIOZ API
# ============================================
def scrape_vevioz(url):
    try:
        api_url = f"https://api.vevioz.com/api/button/mp4/{url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            video_url = data.get('video') or data.get('url')
            if video_url:
                return video_url
        return None
    except Exception as e:
        print(f"vevioz error: {e}")
        return None

# ============================================
# MAIN ENDPOINTS
# ============================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "alive",
        "message": "Use POST /fetch with { 'url': '...' }"
    })

@app.route("/fetch", methods=["POST"])
def fetch():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "URL nahi mila"}), 400
    
    user_url = data["url"].strip()
    
    # ---------- METHOD 1: YOUTUBE ----------
    video_id = extract_youtube_id(user_url)
    if video_id:
        video_url = get_youtube_video(video_id)
        if video_url:
            return jsonify({
                "success": True,
                "downloadUrl": video_url,
                "method": "YouTube Direct"
            })
    
    # ---------- METHOD 2: SAVEFORM.NET (Instagram, TikTok, Facebook) ----------
    video_url = scrape_saveform(user_url)
    if video_url:
        return jsonify({
            "success": True,
            "downloadUrl": video_url,
            "method": "saveform.net"
        })
    
    # ---------- METHOD 3: VEVEIOZ (Backup) ----------
    video_url = scrape_vevioz(user_url)
    if video_url:
        return jsonify({
            "success": True,
            "downloadUrl": video_url,
            "method": "Vevioz API"
        })
    
    # ---------- ALL METHODS FAILED ----------
    return jsonify({
        "success": False,
        "error": "Video nahi mili. Link check karein."
    }), 404

if __name__ == "__main__":
    app.run(debug=True)
