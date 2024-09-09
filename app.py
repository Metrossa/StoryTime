from flask import Flask, request, jsonify, send_file
import os
from storytimev1 import pdf_to_audio
import zipfile
import io
from cartesia import Cartesia

app = Flask(__name__)

# Helper function to get HTML content
def get_html_content(file_name):
    with open(file_name, 'r') as file:
        return file.read()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path == '':
        return get_html_content('index.html')
    elif path == 'features':
        return get_html_content('features.html')
    elif path == 'about':
        return get_html_content('about.html')
    elif path == 'convert':
        return handle_convert()
    elif path == 'download':
        return handle_download()
    else:
        return "Not Found", 404

def handle_convert():
    if request.method != 'POST':
        return jsonify({'error': 'Method not allowed'}), 405

    if 'pdf' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.endswith('.pdf'):
        filename = file.filename
        file_path = '/tmp/' + filename  # Use /tmp for serverless function
        file.save(file_path)
        
        output_dir = '/tmp/output'
        os.makedirs(output_dir, exist_ok=True)
        output_path_prefix = os.path.join(output_dir, 'output_chunk')
        
        try:
            completed_files, text_chunks = pdf_to_audio(file_path, output_path_prefix)
            
            # Create a list of audio file URLs
            audio_urls = [f'/api/audio/{os.path.basename(f)}' for f in completed_files]
            
            # Clean up: remove the uploaded PDF
            os.remove(file_path)
            
            return jsonify({
                'message': 'Conversion successful',
                'audio_files': audio_urls,
                'text_chunks': text_chunks
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Invalid file type'}), 400

def handle_download():
    if request.method != 'POST':
        return jsonify({'error': 'Method not allowed'}), 405

    audio_files = request.json.get('audio_files', [])
    
    if not audio_files:
        return jsonify({'error': 'No audio files to download'}), 400
    
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for file_url in audio_files:
            file_path = os.path.join('/tmp/output', os.path.basename(file_url))
            if os.path.exists(file_path):
                zf.write(file_path, os.path.basename(file_path))
            else:
                app.logger.warning(f"File not found: {file_path}")
    
    if memory_file.getbuffer().nbytes == 0:
        return jsonify({'error': 'No files were added to the zip'}), 404
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='audio_files.zip'
    )

@app.route('/api/audio/<filename>')
def serve_audio(filename):
    return send_file(f'/tmp/output/{filename}', mimetype='audio/mpeg')

if __name__ == '__main__':
    app.run(debug=True)