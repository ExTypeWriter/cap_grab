#!/usr/bin/env python3

from flask import Flask, jsonify, request
from flask_cors import CORS
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize the NEW API interface
api = YouTubeTranscriptApi()

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'YouTube Caption API is running',
        'version': '2.0',
        'api_mode': 'NEW'
    })

@app.route('/api/languages/<video_id>')
def get_languages(video_id):
    """
    Get available caption languages for a video
    
    Returns:
        JSON array of available languages with format:
        [
            {
                "code": "en",
                "name": "English",
                "isAuto": false
            },
            ...
        ]
    """
    try:
        print(f"[INFO] Fetching languages for video: {video_id}")
        
        transcript_list = api.list(video_id)
        
        languages = []
        for transcript in transcript_list:
            lang_data = {
                'code': getattr(transcript, 'language_code', '?'),
                'name': getattr(transcript, 'language', 'Unknown'),
                'isAuto': bool(getattr(transcript, 'is_generated', False))
            }
            languages.append(lang_data)
            print(f"[INFO] Found language: {lang_data['code']} - {lang_data['name']}")
        
        print(f"[INFO] Total languages found: {len(languages)}")
        return jsonify(languages)
        
    except TranscriptsDisabled:
        error_msg = f"Transcripts are disabled for video: {video_id}"
        print(f"[ERROR] {error_msg}")
        return jsonify({'error': error_msg}), 404
        
    except VideoUnavailable:
        error_msg = f"Video unavailable or does not exist: {video_id}"
        print(f"[ERROR] {error_msg}")
        return jsonify({'error': error_msg}), 404
        
    except NoTranscriptFound:
        error_msg = f"No transcripts found for video: {video_id}"
        print(f"[ERROR] {error_msg}")
        return jsonify({'error': error_msg}), 404
        
    except Exception as e:
        error_msg = f"Failed to fetch languages: {str(e)}"
        print(f"[ERROR] {error_msg}")
        
        # Check for rate limiting
        if "429" in str(e) or "Too Many Requests" in str(e):
            return jsonify({'error': 'Rate limited by YouTube. Please try again later.'}), 429
            
        return jsonify({'error': error_msg}), 400

@app.route('/api/captions/<video_id>/<lang_code>')
def get_captions(video_id, lang_code):
    """
    Get captions for a specific language
    
    Returns:
        JSON array of caption segments:
        [
            {
                "text": "Hello world",
                "start": 0.5,
                "duration": 2.3
            },
            ...
        ]
    """
    try:
        print(f"[INFO] Fetching captions for video: {video_id}, language: {lang_code}")
        
        fetched_transcript = api.fetch(video_id, languages=[lang_code])
        
        # Convert to raw data (list of dicts)
        if hasattr(fetched_transcript, 'to_raw_data'):
            captions = fetched_transcript.to_raw_data()
        else:
            captions = [
                {
                    "text": getattr(segment, "text", ""),
                    "start": getattr(segment, "start", 0.0),
                    "duration": getattr(segment, "duration", 0.0)
                }
                for segment in fetched_transcript
            ]
        
        print(f"[INFO] Successfully fetched {len(captions)} caption segments")
        return jsonify(captions)
        
    except TranscriptsDisabled:
        error_msg = f"Transcripts are disabled for video: {video_id}"
        print(f"[ERROR] {error_msg}")
        return jsonify({'error': error_msg}), 404
        
    except VideoUnavailable:
        error_msg = f"Video unavailable or does not exist: {video_id}"
        print(f"[ERROR] {error_msg}")
        return jsonify({'error': error_msg}), 404
        
    except NoTranscriptFound:
        error_msg = f"No transcript found for language '{lang_code}' in video: {video_id}"
        print(f"[ERROR] {error_msg}")
        return jsonify({'error': error_msg}), 404
        
    except Exception as e:
        error_msg = f"Failed to fetch captions: {str(e)}"
        print(f"[ERROR] {error_msg}")
        
        # Check for rate limiting
        if "429" in str(e) or "Too Many Requests" in str(e):
            return jsonify({'error': 'Rate limited by YouTube. Please try again later.'}), 429
            
        return jsonify({'error': error_msg}), 400

@app.route('/api/captions/<video_id>/<lang_code>/translate/<target_lang>')
def get_translated_captions(video_id, lang_code, target_lang):
    """
    Get translated captions (NEW API only feature)
    
    Example: /api/captions/VIDEO_ID/th/translate/en
    """
    try:
        print(f"[INFO] Fetching captions for video: {video_id}, language: {lang_code}, translating to: {target_lang}")
        
        # Get the transcript list first
        transcript_list = api.list(video_id)
        
        # Find the specific transcript
        selected_transcript = None
        for transcript in transcript_list:
            if getattr(transcript, 'language_code', '').lower() == lang_code.lower():
                selected_transcript = transcript
                break
        
        if selected_transcript is None:
            return jsonify({'error': f'Language {lang_code} not found'}), 404
        
        # Translate and fetch
        translated = selected_transcript.translate(target_lang)
        fetched = translated.fetch()
        
        # Convert to raw data
        if hasattr(fetched, 'to_raw_data'):
            captions = fetched.to_raw_data()
        else:
            captions = [
                {
                    "text": getattr(segment, "text", ""),
                    "start": getattr(segment, "start", 0.0),
                    "duration": getattr(segment, "duration", 0.0)
                }
                for segment in fetched
            ]
        
        print(f"[INFO] Successfully translated and fetched {len(captions)} caption segments")
        return jsonify(captions)
        
    except Exception as e:
        error_msg = f"Translation failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return jsonify({'error': error_msg}), 400

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("="*60)
    print("YouTube Caption Fetcher Backend")
    print("Using NEW API Interface")
    print("="*60)
    print("Endpoints:")
    print("  GET  /")
    print("  GET  /api/languages/<video_id>")
    print("  GET  /api/captions/<video_id>/<lang_code>")
    print("  GET  /api/captions/<video_id>/<lang_code>/translate/<target_lang>")
    print("="*60)
    
    # For local development
    app.run(host='0.0.0.0', port=10000, debug=True)