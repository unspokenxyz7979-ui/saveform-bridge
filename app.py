from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)  # Sabhi frontend (Google Sites) ko allow karega

def scrape_saveform(url):
    """saveform.net se download link nikaal kar laayega"""
    try:
        session = requests.Session()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        # 1. Homepage load karein (CSRF token ke liye)
        home = session.get("https://saveform.net/", headers=headers, timeout=10)
        soup = BeautifulSoup(home.text, "html.parser")

        # 2. Token dhoondein
        token = None
        for inp in soup.find_all("input"):
            name = inp.get("name", "")
            if "token" in name or "csrf" in name:
                token = inp.get("value")
                break

        # 3. Form data prepare karein
        data = {"url": url}
        if token:
            data["_token"] = token

        # 4. POST request bhejein (jaise user manually karta hai)
        response = session.post("https://saveform.net/", data=data, headers=headers, timeout=15)
        soup2 = BeautifulSoup(response.text, "html.parser")

        # 5. Download link dhoondein
        dl_link = soup2.find("a", {"id": "download-btn"})
        if not dl_link:
            dl_link = soup2.find("a", class_="download")
        if not dl_link:
            dl_link = soup2.find("a", href=re.compile(r"\.mp4|download"))

        if dl_link and dl_link.get("href"):
            return dl_link["href"]

        # Agar nahi mila toh mp4 link search karein
        mp4_match = re.search(r'https?://[^\s"\']+\.mp4', response.text)
        if mp4_match:
            return mp4_match.group(0)

        return None
    except Exception as e:
        print(f"Scrape error: {e}")
        return None

@app.route("/fetch", methods=["POST"])
def fetch():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "URL nahi mila"}), 400

    video_url = scrape_saveform(data["url"])

    if video_url:
        return jsonify({
            "success": True,
            "downloadUrl": video_url,
            "message": "Video link saveform.net se laaya gaya"
        })
    else:
        return jsonify({
            "success": False,
            "error": "saveform.net se video nahi mila. Link check karein."
        }), 404

# Vercel ke liye yeh zaroori nahi, lekin local test ke liye rakhein
if __name__ == "__main__":
    app.run(debug=True)
