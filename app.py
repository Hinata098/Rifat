from flask import Flask, render_template, request, send_file, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yt_dlp
import os
import re
import logging

app = Flask(__name__)

# Configure rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute"])

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure downloads folder exists
os.makedirs('downloads', exist_ok=True)

def sanitize_filename(title):
    sanitized = re.sub(r'[^a-zA-Z0-9_\- ]', '', title)[:50]
    return sanitized.strip()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preview', methods=['POST'])
@limiter.limit("5 per minute")
def preview():
    url = request.form['url']
    ydl_opts = {'format': 'best', 'quiet': True, 'no_warnings': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info['url']
            title = info.get("title", "Video Preview")
            return render_template('index.html', video_url=video_url, title=title, url=url)
    except yt_dlp.utils.DownloadError:
        logger.error("Download error: unsupported URL or format")
        return jsonify(error="Error: This video format is not supported."), 400
    except Exception as e:
        logger.error(f"Preview error: {e}")
        return jsonify(error="Error: Unable to preview video. Please try again later."), 500

@app.route('/download', methods=['POST'])
@limiter.limit("5 per minute")
def download():
    url = request.form['url']
    format_choice = request.form['format']
    ydl_opts = {
        'format': 'bestaudio/best' if format_choice == 'mp3' else 'bestvideo+bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    if format_choice == 'mp3':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = f"downloads/{sanitize_filename(info['title'])}.{format_choice}"

            if not os.path.exists(filename):
                logger.error(f"File not found: {filename}")
                return jsonify(error="Error: File not found."), 404

            return send_file(filename, as_attachment=True, download_name=os.path.basename(filename))
    except yt_dlp.utils.DownloadError:
        logger.error("Download error: unsupported URL or format")
        return jsonify(error="Error: This video format is not supported."), 400
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify(error="Error: Unable to download video. Please try again later."), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=False)
