from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

# ============================================
# YOUTUBE DOWNLOAD (yt-dlp)
# ============================================
def youtube_download(url):
    """yt-dlp se YouTube video nikaalein - 100% reliable"""
    try:
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')
            if not video_url:
                formats = info.get('formats', [])
                if formats:
                    video_url = formats[-1].get('url')
            return video_url
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return None

# ============================================
# SAVEFORM.NET (Instagram, TikTok, Facebook)
# ============================================
def scrape_saveform(url):
    """saveform.net se Instagram/TikTok/Facebook video nikaalein"""
    try:
        session = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        # Homepage load (CSRF token ke liye)
        home = session.get("https://saveform.net/", headers=headers, timeout=10)
        soup = BeautifulSoup(home.text, "html.parser")
        
        # CSRF token dhoondein
        token = None
        for inp in soup.find_all("input"):
            name = inp.get("name", "")
            if "token" in name or "csrf" in name:
                token = inp.get("value")
                break
        
        # Form data prepare karein
        data = {"url": url}
        if token:
            data["_token"] = token
        
        # POST request bhejein
        response = session.post("https://saveform.net/", data=data, headers=headers, timeout=15)
        soup2 = BeautifulSoup(response.text, "html.parser")
        
        # Download link dhoondein
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
# FALLBACK: SNAPTIK API (TikTok, Instagram)
# ============================================
def scrape_snaptik(url):
    try:
        api_url = f"https://api.snaptik.app/video?url={url}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            video_url = data.get('video_url') or data.get('url') or data.get('data', {}).get('video_url')
            if video_url:
                return video_url
        return None
    except Exception as e:
        print(f"snaptik error: {e}")
        return None

# ============================================
# FALLBACK: VEVEIOZ API (YouTube, Instagram, Facebook)
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
    if 'youtube.com' in user_url or 'youtu.be' in user_url:
        video_url = youtube_download(user_url)
        if video_url:
            return jsonify({
                "success": True,
                "downloadUrl": video_url,
                "method": "yt-dlp"
            })
    
    # ---------- METHOD 2: SAVEFORM.NET (Instagram, TikTok, Facebook) ----------
    video_url = scrape_saveform(user_url)
    if video_url:
        return jsonify({
            "success": True,
            "downloadUrl": video_url,
            "method": "saveform.net"
        })
    
    # ---------- METHOD 3: SNAPTIK (TikTok, Instagram) ----------
    video_url = scrape_snaptik(user_url)
    if video_url:
        return jsonify({
            "success": True,
            "downloadUrl": video_url,
            "method": "Snaptik API"
        })
    
    # ---------- METHOD 4: VEVEIOZ (YouTube, Instagram, Facebook) ----------
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
