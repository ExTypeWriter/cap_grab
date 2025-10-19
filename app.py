from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import os
import time
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

request_cache = {}

app = Flask(__name__)

ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*')
CORS(app, origins=ALLOWED_ORIGINS.split(',') if ALLOWED_ORIGINS != '*' else '*')

def extract_video_id(url: str) -> str:
    m = re.match(r'^https?://(?:www\.)?youtu\.be/([^?&#/]+)', url)
    if m:
        return m.group(1)
    
    parsed = urlparse(url)
    if parsed.netloc.endswith("youtube.com"):
        if parsed.path == "/watch":
            q = parse_qs(parsed.query)
            if "v" in q and q["v"]:
                return q["v"][0]
        m = re.match(r'^/embed/([^/?&#]+)', parsed.path)
        if m:
            return m.group(1)
    
    if re.match(r'^[A-Za-z0-9_-]{11}$', url):
        return url
    
    raise ValueError("Could not extract a valid YouTube video ID from the URL.")

def detect_api_mode():
    try:
        inst = YouTubeTranscriptApi()
        if hasattr(inst, "list") and hasattr(inst, "fetch"):
            return "new", inst
    except TypeError:
        pass
    
    if hasattr(YouTubeTranscriptApi, "list_transcripts") or hasattr(YouTubeTranscriptApi, "get_transcript"):
        return "old", None
    
    try:
        inst = YouTubeTranscriptApi()
        return "new", inst
    except Exception:
        return "old", None

def fmt_time(sec: float) -> str:
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def join_items_raw(items: list, with_timestamps: bool) -> str:
    if with_timestamps:
        lines = [
            f"{fmt_time(it.get('start', 0.0))} - {it.get('text','')}".strip()
            for it in items
            if it.get("text", "").strip()
        ]
    else:
        lines = [it.get("text", "").strip() for it in items if it.get("text", "").strip()]
    return "\n".join(lines).strip()

@app.route('/')
def index():
    return jsonify({
        'service': 'YouTube Caption Fetcher API',
        'version': '1.0',
        'endpoints': {
            'list_transcripts': '/api/list-transcripts [POST]',
            'fetch_transcript': '/api/fetch-transcript [POST]'
        }
    })

@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/api/list-transcripts', methods=['POST'])
def list_transcripts():
    try:
        data = request.json
        url = data.get('url', '')
        
        video_id = extract_video_id(url)
        mode, api = detect_api_mode()
        
        transcripts_data = []
        
        if mode == "new":
            tlist = api.list(video_id)
            for idx, t in enumerate(tlist):
                transcripts_data.append({
                    'index': idx,
                    'code': getattr(t, "language_code", "?"),
                    'name': getattr(t, "language", "?"),
                    'is_auto': bool(getattr(t, "is_generated", False))
                })
        else:
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            for idx, t in enumerate(transcripts):
                transcripts_data.append({
                    'index': idx,
                    'code': getattr(t, "language_code", "?"),
                    'name': getattr(t, "language", "?"),
                    'is_auto': bool(getattr(t, "is_generated", False))
                })
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'transcripts': transcripts_data
        })
        
    except (TranscriptsDisabled, VideoUnavailable, NoTranscriptFound) as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to list transcripts: {str(e)}'}), 500

@app.route('/api/fetch-transcript', methods=['POST'])
def fetch_transcript():
    try:
        data = request.json
        url = data.get('url', '')
        lang = data.get('lang')
        index = data.get('index')
        translate_to = data.get('translate')
        with_timestamps = data.get('timestamps', False)
        
        video_id = extract_video_id(url)
        mode, api = detect_api_mode()
        
        if mode == "new":
            if index is None and translate_to is None and lang:
                langs = [lang] if lang else ["en"]
                fetched = api.fetch(video_id, languages=langs)
                raw = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else [
                    {"text": getattr(s, "text", ""), "start": getattr(s, "start", 0.0)}
                    for s in fetched
                ]
                text = join_items_raw(raw, with_timestamps)
            else:
                tlist = api.list(video_id)
                ts = list(tlist)
                
                if index is not None:
                    selected = ts[index]
                elif lang:
                    selected = tlist.find_transcript([lang])
                else:
                    selected = ts[0]
                
                if translate_to:
                    selected = selected.translate(translate_to)
                
                fetched = selected.fetch()
                raw = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else [
                    {"text": getattr(s, "text", ""), "start": getattr(s, "start", 0.0)}
                    for s in fetched
                ]
                text = join_items_raw(raw, with_timestamps)
        else:
            if index is None and translate_to is None and lang:
                langs = [lang] if lang else ["en"]
                items = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
                text = join_items_raw(items, with_timestamps)
            else:
                transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                ts = list(transcripts)
                
                if index is not None:
                    selected = ts[index]
                elif lang:
                    selected = transcripts.find_transcript([lang])
                else:
                    selected = ts[0]
                
                if translate_to:
                    selected = selected.translate(translate_to)
                
                items = selected.fetch()
                text = join_items_raw(items, with_timestamps)
        
        return jsonify({
            'success': True,
            'transcript': text,
            'video_id': video_id
        })
        
    except (TranscriptsDisabled, VideoUnavailable, NoTranscriptFound) as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to fetch transcript: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)