from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

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
        dl_link = soup2.find("a", {"id": "download-btn"})
        if not dl_link:
            dl_link = soup2.find("a", class_="download")
        if not dl_link:
            dl_link = soup2.find("a", href=re.compile(r"\.mp4|download"))
        if dl_link and dl_link.get("href"):
            return dl_link["href"]
        mp4_match = re.search(r'https?://[^\s"\']+\.mp4', response.text)
        if mp4_match:
            return mp4_match.group(0)
        return None
    except Exception as e:
        print(f"Saveform error: {e}")
        return None

def fallback_api(url):
    """Method 2: Agar saveform.net fail ho toh yeh API use karein"""
    try:
        # Yeh API YouTube, Instagram, TikTok, Facebook par kaam karti hai
        api_url = f"https://api.vevioz.com/api/button/mp4/{url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            video_url = data.get('video') or data.get('url')
            if video_url:
                return video_url
        return None
    except Exception as e:
        print(f"Fallback error: {e}")
        return None

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "alive", "message": "Backend is running. Use POST /fetch"})

@app.route("/fetch", methods=["POST"])
def fetch():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "URL nahi mila"}), 400
    
    user_url = data["url"]
    
    # 1. Pehle saveform.net try karein
    video_url = scrape_saveform(user_url)
    if video_url:
        return jsonify({"success": True, "downloadUrl": video_url, "method": "saveform.net"})
    
    # 2. Agar saveform fail ho toh fallback API try karein
    video_url = fallback_api(user_url)
    if video_url:
        return jsonify({"success": True, "downloadUrl": video_url, "method": "Fallback API"})
    
    return jsonify({"success": False, "error": "Koi bhi method kaam nahi kiya. Link check karein."}), 404
