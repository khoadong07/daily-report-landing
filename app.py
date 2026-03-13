from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, make_response, Blueprint
import os
import json
import uuid
import requests
import re
import pandas as pd
from datetime import datetime, timedelta
import base64
from dotenv import load_dotenv
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure for reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure URL prefix for reverse proxy
URL_PREFIX = os.getenv('APPLICATION_ROOT', '')
if URL_PREFIX and not URL_PREFIX.startswith('/'):
    URL_PREFIX = '/' + URL_PREFIX
if URL_PREFIX == '/':
    URL_PREFIX = ''

# Create Blueprint with URL prefix if needed
if URL_PREFIX:
    bp = Blueprint('main', __name__, url_prefix=URL_PREFIX)
else:
    bp = Blueprint('main', __name__)

# Configuration from environment variables
API_BASE_URL = os.getenv('API_BASE_URL')
API_GENERATE_ENDPOINT = os.getenv('API_GENERATE_ENDPOINT', '/api/generate-daily')
API_HEALTH_ENDPOINT = os.getenv('API_HEALTH_ENDPOINT', '/health')
APP_BASE_URL = os.getenv('APP_BASE_URL', 'http://localhost:8000')
API_TIMEOUT = int(os.getenv('API_TIMEOUT', '300'))
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Deployment configuration
DEPLOYMENT_ENV = os.getenv('DEPLOYMENT_ENV', 'development')
EXTERNAL_URL = os.getenv('EXTERNAL_URL', APP_BASE_URL)

# Authentication configuration
LOGIN_USERNAME = os.getenv('LOGIN_USERNAME', 'admin')
LOGIN_PASSWORD = os.getenv('LOGIN_PASSWORD', 'password')
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

# Flask configuration
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=60)  # 60 minutes session

# Helper function to generate URLs with APPLICATION_ROOT
# Helper function to generate URLs (simplified since we use Blueprint)
def url_for_with_prefix(endpoint, **values):
    """Generate URL - Blueprint handles prefix automatically"""
    if not endpoint.startswith('main.'):
        endpoint = 'main.' + endpoint
    return url_for(endpoint, **values)

# Context processor to provide external URL to templates
@app.context_processor
def inject_external_url():
    return {
        'external_url': EXTERNAL_URL,
        'deployment_env': DEPLOYMENT_ENV,
        'url_for_with_prefix': url_for_with_prefix
    }

# Add no-cache headers for protected routes
@app.after_request
def add_no_cache_headers(response):
    # Only add no-cache headers for HTML pages that require login
    if (request.endpoint and 
        request.endpoint not in ['login', 'static'] and 
        'logged_in' in session and session['logged_in']):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

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

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for_with_prefix('login'))
        
        # Check if session is expired
        if 'login_time' in session:
            login_time = datetime.fromisoformat(session['login_time'])
            if datetime.now() - login_time > timedelta(minutes=60):
                session.clear()
                return redirect(url_for_with_prefix('login'))
        
        return f(*args, **kwargs)
    return decorated_function

REPORTS_DIR = 'reports'
LOGOS_DIR = 'static/logos'
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(LOGOS_DIR, exist_ok=True)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
            session.permanent = True
            session['logged_in'] = True
            session['username'] = username
            session['login_time'] = datetime.now().isoformat()
            
            # Redirect to the page user was trying to access, or home
            next_page = request.args.get('next')
            return redirect(next_page or url_for_with_prefix('index'))
        else:
            response = make_response(render_template('login.html', error='Invalid username or password'))
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
    
    # If already logged in, redirect to home
    if 'logged_in' in session and session['logged_in']:
        return redirect(url_for_with_prefix('index'))
    
    response = make_response(render_template('login.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@bp.route('/logout')
def logout():
    session.clear()
    response = make_response(redirect(url_for_with_prefix('login')))
    # Clear cache to prevent back button access
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@bp.route('/')
@login_required
def index():
    response = make_response(render_template('index.html'))
    # Prevent caching to avoid back button issues
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@bp.route('/api/test-connection')
@login_required
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

@bp.route('/api/test-logo-upload', methods=['POST'])
@login_required
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
        logo_url = f"/static/logos/{logo_filename}"
        
        return jsonify({
            'success': True,
            'message': 'Logo uploaded successfully',
            'logo_url': logo_url,
            'logo_path': logo_path
        })
        
    except Exception as e:
        print(f"Error in test logo upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/static/logos/<filename>')
@login_required
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

@bp.route('/api/extract-topics', methods=['POST'])
@login_required
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

@bp.route('/api/generate-from-upload', methods=['POST'])
@login_required
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
                        logo_url = f"/static/logos/{logo_filename}"
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
        
        # Reorder slide_1 data: buzz -> post -> comments
        if 'slide_1' in api_data and 'data' in api_data['slide_1']:
            slide_1_data = api_data['slide_1']['data']
            
            # Create a mapping for desired order
            order_mapping = {'buzz': 0, 'post': 1, 'comments': 2}
            
            # Sort the data based on the type field
            api_data['slide_1']['data'] = sorted(
                slide_1_data, 
                key=lambda x: order_mapping.get(x.get('type', 'unknown'), 999)
            )
            
            print("Slide 1 data reordered successfully")
        
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

@bp.route('/generate-report')
@login_required
def generate_report():
    """Generate report from data.json using template"""
    try:
        # Load data from JSON file
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reorder slide_1 data: buzz -> post -> comments
        if 'slide_1' in data and 'data' in data['slide_1']:
            slide_1_data = data['slide_1']['data']
            
            # Create a mapping for desired order
            order_mapping = {'buzz': 0, 'post': 1, 'comments': 2}
            
            # Sort the data based on the type field
            data['slide_1']['data'] = sorted(
                slide_1_data, 
                key=lambda x: order_mapping.get(x.get('type', 'unknown'), 999)
            )
            
            print("Slide 1 data reordered successfully")
        
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

@bp.route('/preview')
@login_required
def preview_report():
    """Preview report without saving"""
    try:
        # Load data from JSON file
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reorder slide_1 data: buzz -> post -> comments
        if 'slide_1' in data and 'data' in data['slide_1']:
            slide_1_data = data['slide_1']['data']
            
            # Create a mapping for desired order
            order_mapping = {'buzz': 0, 'post': 1, 'comments': 2}
            
            # Sort the data based on the type field
            data['slide_1']['data'] = sorted(
                slide_1_data, 
                key=lambda x: order_mapping.get(x.get('type', 'unknown'), 999)
            )
        
        # Render template directly for preview
        return render_template('report_template.html', **data)
    except Exception as e:
        return f"Error loading preview: {str(e)}", 500

@bp.route('/api/save', methods=['POST'])
@login_required
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

@bp.route('/report/<filename>')
def view_report(filename):
    filepath = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return "Report not found", 404

@bp.route('/api/reports')
@login_required
def list_reports():
    files = os.listdir(REPORTS_DIR)
    reports = [{'filename': f, 'url': f"/report/{f}"} for f in files if f.endswith('.html')]
    return jsonify(reports)

# Register Blueprint
app.register_blueprint(bp)

if __name__ == '__main__':
    print(f"Starting server on {HOST}:{PORT}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"App Base URL: {APP_BASE_URL}")
    print(f"URL Prefix: {URL_PREFIX}")
    print(f"Debug mode: {DEBUG}")
    if URL_PREFIX:
        print(f"Login URL: http://localhost:{PORT}{URL_PREFIX}/login")
    else:
        print(f"Login URL: http://localhost:{PORT}/login")
    print(f"Login Username: {LOGIN_USERNAME}")
    print("=" * 50)
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)