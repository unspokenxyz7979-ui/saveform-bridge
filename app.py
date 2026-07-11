from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import json
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

# ---------- YOUTUBE VIDEO ID EXTRACTOR ----------
def extract_youtube_id(url):
    """YouTube URL se video ID nikaalein"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([\w-]+)',
        r'(?:youtu\.be\/)([\w-]+)',
        r'(?:youtube\.com\/shorts\/)([\w-]+)',
        r'(?:youtube\.com\/embed\/)([\w-]+)',
        r'(?:youtube\.com\/v\/)([\w-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# ---------- YOUTUBE DIRECT DOWNLOAD ----------
def get_youtube_video(video_id):
    """YouTube video ka direct URL nikaalein - WORKING METHOD"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Pehle video page load karein
        player_url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(player_url, headers=headers, timeout=15)
        
        # ytInitialPlayerResponse JSON nikaalein
        match = re.search(r'var ytInitialPlayerResponse = ({.*?});', response.text, re.DOTALL)
        if not match:
            # Alternate pattern
            match = re.search(r'ytInitialPlayerResponse\s*=\s*({.*?});', response.text, re.DOTALL)
        
        if match:
            data = json.loads(match.group(1))
            
            # Check if video is playable
            playability = data.get('playabilityStatus', {})
            if playability.get('status') == 'UNPLAYABLE':
                print(f"Video not playable: {playability.get('reason')}")
                return None
            
            # Streaming data se URLs nikaalein
            streaming = data.get('streamingData', {})
            if not streaming:
                return None
            
            # Sab formats collect karein
            all_formats = streaming.get('formats', []) + streaming.get('adaptiveFormats', [])
            
            # Best quality URL select karein (1080p -> 720p -> 480p -> 360p)
            best_url = None
            best_quality = 0
            
            for fmt in all_formats:
                if 'url' in fmt:
                    # Quality label se resolution nikaalein
                    quality = 0
                    if fmt.get('qualityLabel'):
                        q_str = fmt['qualityLabel'].replace('p', '').replace('60', '').strip()
                        if q_str.isdigit():
                            quality = int(q_str)
                    
                    # Agar quality nahi hai toh height se try karein
                    if quality == 0 and fmt.get('height'):
                        quality = fmt['height']
                    
                    if quality > best_quality:
                        best_quality = quality
                        best_url = fmt['url']
            
            if best_url:
                return best_url
            
            # Agar koi URL na mile toh first URL return karein
            for fmt in all_formats:
                if 'url' in fmt:
                    return fmt['url']
        
        # Agar JSON na mile toh HTML mein se googlevideo URL nikaalein
        url_pattern = r'https?://[^"]+\.googlevideo\.com/[^"]+'
        matches = re.findall(url_pattern, response.text)
        if matches:
            # Sab se lamba URL (usually best quality)
            return max(matches, key=len)
        
        return None
    except Exception as e:
        print(f"YouTube error: {e}")
        return None

# ---------- SAVEFORM.NET (Instagram, TikTok, Facebook) ----------
def scrape_saveform(url):
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # Homepage load (CSRF token ke liye)
        home = session.get("https://saveform.net/", headers=headers, timeout=10)
        soup = BeautifulSoup(home.text, "html.parser")
        
        # Token dhoondein
        token = None
        for inp in soup.find_all("input"):
            name = inp.get("name", "")
            if "token" in name or "csrf" in name:
                token = inp.get("value")
                break
        
        # Data prepare karein
        data = {"url": url}
        if token:
            data["_token"] = token
        
        # POST request bhejein
        response = session.post("https://saveform.net/", data=data, headers=headers, timeout=15)
        
        # Download link dhoondein
        soup2 = BeautifulSoup(response.text, "html.parser")
        
        # Common patterns
        dl_link = soup2.find("a", {"id": "download-btn"})
        if not dl_link:
            dl_link = soup2.find("a", class_="download")
        if not dl_link:
            dl_link = soup2.find("a", href=re.compile(r"download|video|mp4"))
        
        if dl_link and dl_link.get("href"):
            return dl_link["href"]
        
        # Agar nahi mila toh mp4 link search karein
        mp4_match = re.search(r'https?://[^\s"\']+\.mp4', response.text)
        if mp4_match:
            return mp4_match.group(0)
        
        return None
    except Exception as e:
        print(f"Saveform error: {e}")
        return None

# ---------- MAIN ENDPOINTS ----------
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
    
    # ---------- METHOD 1: YouTube ----------
    video_id = extract_youtube_id(user_url)
    if video_id:
        video_url = get_youtube_video(video_id)
        if video_url:
            return jsonify({
                "success": True,
                "downloadUrl": video_url,
                "method": "YouTube Direct"
            })
    
    # ---------- METHOD 2: saveform.net (Instagram, TikTok, Facebook) ----------
    video_url = scrape_saveform(user_url)
    if video_url:
        return jsonify({
            "success": True,
            "downloadUrl": video_url,
            "method": "saveform.net"
        })
    
    # ---------- METHOD 3: YouTube Backup (Direct HTML) ----------
    if video_id:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            player_url = f"https://www.youtube.com/watch?v={video_id}"
            response = requests.get(player_url, headers=headers, timeout=15)
            
            # Direct googlevideo URL search
            matches = re.findall(r'https?://[^"]+\.googlevideo\.com/[^"]+', response.text)
            if matches:
                return jsonify({
                    "success": True,
                    "downloadUrl": max(matches, key=len),
                    "method": "YouTube Backup"
                })
        except:
            pass
    
    # ---------- ALL METHODS FAILED ----------
    return jsonify({
        "success": False,
        "error": "Video nahi mili. Link check karein."
    }), 404

if __name__ == "__main__":
    app.run(debug=True)
