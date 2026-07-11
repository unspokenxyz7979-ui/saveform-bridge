from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import re

app = Flask(__name__)
CORS(app)

def download_video(url):
    """yt-dlp se video download karein - Sab platforms ke liye"""
    try:
        # Temp folder banayein
        temp_dir = tempfile.mkdtemp()
        
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Video info aur download
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if os.path.exists(filename):
                return filename, info.get('title', 'video')
            return None, None
            
    except Exception as e:
        print(f"Download error: {e}")
        return None, None

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "alive",
        "message": "POST /download with { 'url': '...' }"
    })

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "URL nahi mila"}), 400
    
    url = data["url"].strip()
    
    # Video download karein
    filename, title = download_video(url)
    
    if filename:
        # Video file send karein
        return send_file(
            filename,
            as_attachment=True,
            download_name=f"{title}.mp4"
        )
    else:
        return jsonify({
            "success": False,
            "error": "Video download nahi ho paai. Link check karein."
        }), 404

if __name__ == "__main__":
    app.run(debug=True)
