from flask import Flask, render_template, request, jsonify
import os
import uuid
from datetime import datetime

app = Flask(__name__)

REPORTS_DIR = 'reports'
os.makedirs(REPORTS_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/save', methods=['POST'])
def save_report():
    data = request.json
    html_content = data.get('html', '')
    title = data.get('title', 'report')
    
    if not html_content:
        return jsonify({'error': 'HTML content is required'}), 400
    
    # Generate unique filename
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f"{title}-{timestamp}.html"
    filepath = os.path.join(REPORTS_DIR, filename)
    
    # Save HTML file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Generate access URL with proper host
    url = f"/report/{filename}"
    host = request.host.replace('0.0.0.0', 'localhost')  # Fix 0.0.0.0 issue
    
    return jsonify({
        'success': True,
        'filename': filename,
        'url': url,
        'full_url': f"http://{host}{url}"
    })

@app.route('/report/<filename>')
def view_report(filename):
    filepath = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return "Report not found", 404

@app.route('/api/reports')
def list_reports():
    files = os.listdir(REPORTS_DIR)
    reports = [{'filename': f, 'url': f"/report/{f}"} for f in files if f.endswith('.html')]
    return jsonify(reports)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)