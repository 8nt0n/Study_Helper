import os
import random
import threading
from flask import Flask, render_template, send_from_directory, jsonify

# Import your library
import lib_create_videos 

app = Flask(__name__)

# Folders
VIDEO_FOLDER = 'videos'

@app.route('/')
def index():
    if not os.path.exists(VIDEO_FOLDER):
        os.makedirs(VIDEO_FOLDER)
        
    files = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith('.mp4')]
    random.shuffle(files)
    
    return render_template('index.html', videos=files)

@app.route('/create')
def create_page():
    return render_template('create.html')

@app.route('/api/generate', methods=['POST'])
def generate_videos():
    # Run your 20-minute script in a background thread 
    # so the web server doesn't freeze or time out.
    thread = threading.Thread(target=lib_create_videos.main)
    thread.daemon = True
    thread.start()
    
    # Immediately tell the frontend that the job started
    return jsonify({"status": "success", "message": "Video generation started in the background."})

@app.route('/videos/<filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_FOLDER, filename)

@app.route('/quiz/<filename>')
def serve_quiz(filename):
    base_name = os.path.splitext(filename)[0]
    json_filename = f"{base_name}.json"
    
    if os.path.exists(os.path.join(VIDEO_FOLDER, json_filename)):
        return send_from_directory(VIDEO_FOLDER, json_filename)
    
    return jsonify({"error": "Quiz not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)