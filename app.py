from flask import Flask, render_template, request, jsonify
import os
import json
import uuid
import requests
import re
import pandas as pd
from datetime import datetime
import base64
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration from environment variables
API_BASE_URL = os.getenv('API_BASE_URL', 'http://148.113.218.245:8524')
API_GENERATE_ENDPOINT = os.getenv('API_GENERATE_ENDPOINT', '/api/generate-daily')
API_HEALTH_ENDPOINT = os.getenv('API_HEALTH_ENDPOINT', '/health')
APP_BASE_URL = os.getenv('APP_BASE_URL', 'https://service-ai.radaa.net/daily')
API_TIMEOUT = int(os.getenv('API_TIMEOUT', '300'))
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Custom filter to convert markdown links to HTML
@app.template_filter('markdown_links')
def markdown_links_filter(text):
    """Convert markdown links [text](url) to HTML <a> tags"""
    if not text:
        return text
    
    # Pattern to match [text](url)
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    
    def replace_link(match):
        link_text = match.group(1)
        url = match.group(2)
        return f'<a href="{url}" target="_blank">{link_text}</a>'
    
    # Replace all markdown links with HTML links
    result = re.sub(pattern, replace_link, text)
    return result

REPORTS_DIR = 'reports'
LOGOS_DIR = 'static/logos'
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(LOGOS_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/test-connection')
def test_connection():
    """Test connection to external API"""
    try:
        import time
        start_time = time.time()
        
        # Test API endpoint using environment variable
        test_url = f"{API_BASE_URL}{API_HEALTH_ENDPOINT}"
        
        # Simple GET request to check if API is reachable
        response = requests.get(test_url, timeout=10)
        
        end_time = time.time()
        response_time = int((end_time - start_time) * 1000)
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'message': 'API connection successful',
                'response_time': response_time,
                'status_code': response.status_code,
                'api_url': test_url
            })
        else:
            return jsonify({
                'success': False,
                'error': f'API returned status code {response.status_code}',
                'response_time': response_time,
                'api_url': test_url
            })
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Connection timeout - API server may be down',
            'api_url': test_url
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Cannot connect to API server - check internet connection',
            'api_url': test_url
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}',
            'api_url': test_url if 'test_url' in locals() else 'Unknown'
        })

@app.route('/api/test-logo-upload', methods=['POST'])
def test_logo_upload():
    """Test logo upload functionality"""
    try:
        print("=== Testing logo upload ===")
        print(f"Files in request: {list(request.files.keys())}")
        
        if 'brand_logo' not in request.files:
            return jsonify({'error': 'No logo file in request'}), 400
        
        logo_file = request.files['brand_logo']
        print(f"Logo filename: {logo_file.filename}")
        print(f"Logo content type: {logo_file.content_type}")
        
        if logo_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Test save
        logo_filename = f"test_logo_{uuid.uuid4().hex[:8]}.png"
        logo_path = os.path.join(LOGOS_DIR, logo_filename)
        
        logo_file.save(logo_path)
        logo_url = f"/daily/static/logos/{logo_filename}"
        
        return jsonify({
            'success': True,
            'message': 'Logo uploaded successfully',
            'logo_url': logo_url,
            'logo_path': logo_path
        })
        
    except Exception as e:
        print(f"Error in test logo upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/daily/static/logos/<filename>')
def serve_logo(filename):
    """Serve logo files"""
    try:
        logo_path = os.path.join(LOGOS_DIR, filename)
        if os.path.exists(logo_path):
            from flask import send_file
            return send_file(logo_path)
        else:
            return "Logo not found", 404
    except Exception as e:
        print(f"Error serving logo {filename}: {str(e)}")
        return "Error serving logo", 500

@app.route('/daily/static/<filename>')
def serve_static(filename):
    """Serve static files"""
    try:
        static_path = os.path.join('static', filename)
        if os.path.exists(static_path):
            from flask import send_file
            return send_file(static_path)
        else:
            return "File not found", 404
    except Exception as e:
        print(f"Error serving static file {filename}: {str(e)}")
        return "Error serving static file", 500

@app.route('/api/extract-topics', methods=['POST'])
def extract_topics():
    """Extract unique topics from uploaded Excel file"""
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file extension
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({'error': 'Please upload an Excel file (.xlsx or .xls)'}), 400
        
        # Read Excel file
        try:
            df = pd.read_excel(file)
        except Exception as e:
            return jsonify({'error': f'Error reading Excel file: {str(e)}'}), 400
        
        # Check if 'Topic' column exists
        if 'Topic' not in df.columns:
            available_columns = list(df.columns)
            return jsonify({
                'error': 'Column "Topic" not found in Excel file',
                'available_columns': available_columns
            }), 400
        
        # Get unique topics, remove NaN values and convert to list
        unique_topics = df['Topic'].dropna().unique().tolist()
        
        # Sort topics alphabetically
        unique_topics.sort()
        
        return jsonify({
            'success': True,
            'topics': unique_topics,
            'total_rows': len(df),
            'total_topics': len(unique_topics)
        })
        
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/api/generate-from-upload', methods=['POST'])
def generate_from_upload():
    """Generate report by uploading file to external API"""
    try:
        print("=== Starting generate_from_upload ===")
        
        # Check if file is present
        if 'file' not in request.files:
            print("Error: No file uploaded")
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            print("Error: No file selected")
            return jsonify({'error': 'No file selected'}), 400
        
        # Handle logo upload (optional)
        logo_url = None
        if 'brand_logo' in request.files:
            logo_file = request.files['brand_logo']
            print(f"Logo file received: {logo_file.filename}")
            
            if logo_file.filename != '':
                # Validate logo file type
                allowed_extensions = {'.png', '.jpg', '.jpeg', '.svg'}
                file_ext = os.path.splitext(logo_file.filename)[1].lower()
                
                print(f"Logo file extension: {file_ext}")
                
                if file_ext in allowed_extensions:
                    # Generate unique filename for logo
                    logo_filename = f"logo_{uuid.uuid4().hex[:8]}{file_ext}"
                    logo_path = os.path.join(LOGOS_DIR, logo_filename)
                    
                    try:
                        logo_file.save(logo_path)
                        logo_url = f"/daily/static/logos/{logo_filename}"
                        print(f"Logo saved successfully: {logo_path}")
                        print(f"Logo URL: {logo_url}")
                    except Exception as e:
                        print(f"Error saving logo: {str(e)}")
                        # Continue without logo if save fails
                else:
                    print(f"Invalid logo file type: {file_ext}")
                    # Continue without logo if invalid type
            else:
                print("Logo file is empty")
        else:
            print("No logo file in request")
        
        # Get form parameters
        brand_name = request.form.get('brand_name', '')
        report_name = request.form.get('report_name', '')
        report_date = request.form.get('report_date', '')
        report_time = request.form.get('report_time', '10:00')
        show_interactions = 'false'  # Default value
        
        print(f"Parameters: brand_name={brand_name}, report_name={report_name}, report_date={report_date}")
        
        if not brand_name or not report_name or not report_date:
            print("Error: Missing required parameters")
            return jsonify({'error': 'Brand name, report name and report date are required'}), 400
        
        # Prepare the API call using environment variables
        api_url = f"{API_BASE_URL}{API_GENERATE_ENDPOINT}"
        print(f"Calling API: {api_url}")
        
        # Reset file pointer to beginning
        file.seek(0)
        
        # Prepare files and data for the API call
        files = {
            'file': (file.filename, file.stream, file.content_type)
        }
        
        data = {
            'brand_name': brand_name,
            'report_date': report_date,
            'report_time': report_time,
            'show_interactions': False
        }
        
        print("Making API request...")
        
        # Call the external API with timeout from environment
        try:
            response = requests.post(api_url, files=files, data=data, timeout=API_TIMEOUT)
            print(f"API Response Status: {response.status_code}")
            
        except requests.exceptions.Timeout:
            print("API request timed out")
            return jsonify({'error': f'API request timed out after {API_TIMEOUT} seconds. The server may be busy, please try again later.'}), 500
        except requests.exceptions.ConnectionError:
            print("Connection error to API")
            return jsonify({'error': 'Cannot connect to the API server. Please check your internet connection.'}), 500
        except requests.exceptions.RequestException as e:
            print(f"Request exception: {str(e)}")
            return jsonify({'error': f'API request failed: {str(e)}'}), 500
        
        if response.status_code != 200:
            error_text = response.text[:500]  # Limit error text length
            print(f"API Error: {response.status_code} - {error_text}")
            return jsonify({'error': f'API call failed with status {response.status_code}. Please try again.'}), 500
        
        # Get the JSON data from API response
        try:
            api_response = response.json()
            print("API response parsed successfully")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return jsonify({'error': 'API returned invalid JSON response'}), 500
        
        # Extract the "data" field which contains the actual report data
        if 'data' not in api_response:
            print("Error: API response missing 'data' field")
            print(f"API Response keys: {list(api_response.keys())}")
            return jsonify({'error': 'API response format is invalid (missing data field)'}), 500
        
        api_data = api_response['data']
        print("API data extracted successfully")
        
        # Add report_name and logo to the data for template rendering
        if 'report_metadata' not in api_data:
            api_data['report_metadata'] = {}
        api_data['report_metadata']['report_name'] = report_name
        if logo_url:
            api_data['report_metadata']['brand_logo'] = logo_url
        
        # Generate HTML report using template
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        # Use report_name for filename instead of brand_name
        report_slug = report_name.lower().replace(' ', '-').replace('ă', 'a').replace('ầ', 'au').replace('đ', 'd')
        # Remove special characters for filename
        report_slug = re.sub(r'[^\w\-]', '', report_slug)
        filename = f"{report_slug}-{timestamp}.html"
        
        print(f"Generating report with filename: {filename}")
        
        # Render the template with API data
        try:
            html_content = render_template('report_template.html', **api_data)
            print("Template rendered successfully")
        except Exception as e:
            print(f"Template rendering error: {str(e)}")
            return jsonify({'error': f'Error generating report template: {str(e)}'}), 500
        
        # Save the report
        report_path = os.path.join(REPORTS_DIR, filename)
        try:
            with open(report_path, 'w', encoding='utf-8') as report_file:
                report_file.write(html_content)
            print(f"Report saved to: {report_path}")
        except Exception as e:
            print(f"File save error: {str(e)}")
            return jsonify({'error': f'Error saving report file: {str(e)}'}), 500
        
        # Generate access URL using environment variable
        url = f"/report/{filename}"
        # Use APP_BASE_URL from environment, fallback to request host
        if APP_BASE_URL and APP_BASE_URL != 'http://localhost:8000':
            full_url = f"{APP_BASE_URL}{url}"
        else:
            host = request.host.replace('0.0.0.0', 'localhost')
            full_url = f"http://{host}{url}"
        
        print(f"Report generated successfully: {full_url}")
        
        return jsonify({
            'success': True,
            'filename': filename,
            'url': url,
            'full_url': full_url,
            'path': report_path
        })
        
    except Exception as e:
        print(f"Unexpected error in generate_from_upload: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Unexpected server error: {str(e)}'}), 500

@app.route('/generate-report')
def generate_report():
    """Generate report from data.json using template"""
    try:
        # Load data from JSON file
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Generate HTML report using template
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        brand_slug = data['report_metadata']['brand'].lower().replace(' ', '-').replace('ă', 'a').replace('ầ', 'au')
        filename = f"{brand_slug}-{timestamp}.html"
        
        # Render the template with data
        html_content = render_template('report_template.html', **data)
        
        # Save the report
        report_path = os.path.join(REPORTS_DIR, filename)
        with open(report_path, 'w', encoding='utf-8') as report_file:
            report_file.write(html_content)
        
        # Generate access URL using environment variable
        url = f"/report/{filename}"
        # Use APP_BASE_URL from environment, fallback to request host
        if APP_BASE_URL and APP_BASE_URL != 'http://localhost:8000':
            full_url = f"{APP_BASE_URL}{url}"
        else:
            host = request.host.replace('0.0.0.0', 'localhost')
            full_url = f"http://{host}{url}"
        
        return jsonify({
            'success': True,
            'filename': filename,
            'url': url,
            'full_url': full_url,
            'path': report_path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/preview')
def preview_report():
    """Preview report without saving"""
    try:
        # Load data from JSON file
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Render template directly for preview
        return render_template('report_template.html', **data)
    except Exception as e:
        return f"Error loading preview: {str(e)}", 500

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
    
    # Generate access URL using environment variable
    url = f"/report/{filename}"
    # Use APP_BASE_URL from environment, fallback to request host
    if APP_BASE_URL and APP_BASE_URL != 'http://localhost:8000':
        full_url = f"{APP_BASE_URL}{url}"
    else:
        host = request.host.replace('0.0.0.0', 'localhost')  # Fix 0.0.0.0 issue
        full_url = f"http://{host}{url}"
    
    return jsonify({
        'success': True,
        'filename': filename,
        'url': url,
        'full_url': full_url
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
    print(f"Starting server on {HOST}:{PORT}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"App Base URL: {APP_BASE_URL}")
    print(f"Debug mode: {DEBUG}")
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)