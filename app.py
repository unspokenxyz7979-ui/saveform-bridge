from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import json

app = Flask(__name__)
CORS(app)

# ---------- METHOD 1: saveform.net ----------
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
        print(f"Saveform error: {e}")
        return None

# ---------- METHOD 2: vevioz (YouTube, Instagram, TikTok) ----------
def fallback_vevioz(url):
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
        print(f"Vevioz error: {e}")
        return None

# ---------- METHOD 3: snaptik (TikTok, Instagram, YouTube) ----------
def fallback_snaptik(url):
    try:
        # Snaptik API (public)
        api_url = f"https://api.snaptik.app/video?url={url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Snaptik returns video URL in different keys
            video_url = data.get('video_url') or data.get('url') or data.get('data', {}).get('video_url')
            if video_url:
                return video_url
        return None
    except Exception as e:
        print(f"Snaptik error: {e}")
        return None

# ---------- METHOD 4: youtube-mp3 (for YouTube) ----------
def fallback_youtube(url):
    try:
        # A simple YouTube download API (may have limits)
        api_url = f"https://www.youtube-mp3.com/api/video?url={url}&format=mp4"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            video_url = data.get('downloadUrl') or data.get('url')
            if video_url:
                return video_url
        return None
    except Exception as e:
        print(f"YouTube error: {e}")
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
    methods = [
        ("saveform.net", scrape_saveform),
        ("vevioz", fallback_vevioz),
        ("snaptik", fallback_snaptik),
        ("youtube-mp3", fallback_youtube)
    ]

    for name, func in methods:
        print(f"Trying {name}...")
        video_url = func(user_url)
        if video_url:
            return jsonify({
                "success": True,
                "downloadUrl": video_url,
                "method": name
            })

    return jsonify({
        "success": False,
        "error": "تمام طریقے ناکام ہو گئے۔ لنک چیک کریں یا دوسرا پلیٹ فارم آزمائیں۔"
    }), 404
