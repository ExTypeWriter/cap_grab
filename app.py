from flask import Flask, request, jsonify
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'status': 'YouTube Caption API is running'})

@app.route('/api/languages/<video_id>')
def get_languages(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        languages = []
        for t in transcript_list:
            languages.append({
                'code': t.language_code,
                'name': t.language,
                'isAuto': t.is_generated
            })
        return jsonify(languages)
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/captions/<video_id>/<lang>')
def get_captions(video_id, lang):
    try:
        captions = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
        return jsonify(captions)
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)