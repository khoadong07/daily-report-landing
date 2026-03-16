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

# Get the absolute path to the current directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Configuration from environment variables
API_BASE_URL = os.getenv('API_BASE_URL', 'http://148.113.218.245:8524')
API_GENERATE_ENDPOINT = os.getenv('API_GENERATE_ENDPOINT', '/api/generate-daily')
API_HEALTH_ENDPOINT = os.getenv('API_HEALTH_ENDPOINT', '/health')
APP_BASE_URL = os.getenv('APP_BASE_URL', 'https://service-ai.radaa.net/daily')
STATIC_URL_PREFIX = os.getenv('STATIC_URL_PREFIX', '')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
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

def generate_static_url(path):
    """Generate proper static URL with correct prefix for both development and production"""
    # Clean the path - remove leading slashes
    clean_path = path.lstrip('/')
    
    if ENVIRONMENT == 'production':
        # In production, always use the /daily prefix
        return f"/daily/static/{clean_path}"
    else:
        # In development, use simple static path
        return f"/static/{clean_path}"

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
        logo_url = f"{STATIC_URL_PREFIX}/static/logos/{logo_filename}"
        
        return jsonify({
            'success': True,
            'message': 'Logo uploaded successfully',
            'logo_url': logo_url,
            'logo_path': logo_path
        })
        
    except Exception as e:
        print(f"Error in test logo upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Routes for static files - support both local and production
@app.route('/static/logos/<filename>')
@app.route('/daily/static/logos/<filename>')
def serve_logo(filename):
    """Serve logo files with proper headers and MIME types"""
    print(f"Serving logo: {filename}")
    try:
        logo_path = os.path.join(LOGOS_DIR, filename)
        print(f"Logo path: {logo_path}")
        print(f"Logo exists: {os.path.exists(logo_path)}")
        
        if os.path.exists(logo_path):
            from flask import send_file
            
            # Determine proper MIME type
            if filename.lower().endswith('.png'):
                mimetype = 'image/png'
            elif filename.lower().endswith(('.jpg', '.jpeg')):
                mimetype = 'image/jpeg'
            elif filename.lower().endswith('.svg'):
                mimetype = 'image/svg+xml'
            elif filename.lower().endswith('.gif'):
                mimetype = 'image/gif'
            elif filename.lower().endswith('.webp'):
                mimetype = 'image/webp'
            else:
                mimetype = 'application/octet-stream'
            
            response = send_file(
                logo_path,
                mimetype=mimetype,
                as_attachment=False
            )
            # Set cache headers manually
            response.cache_control.max_age = 31536000  # 1 year cache
            return response
        else:
            print(f"Logo file not found: {logo_path}")
            return "Logo not found", 404
    except Exception as e:
        print(f"Error serving logo {filename}: {str(e)}")
        return "Error serving logo", 500

@app.route('/static/<filename>')
@app.route('/daily/static/<filename>')
def serve_static(filename):
    """Serve static files with proper headers and MIME types"""
    print(f"Serving static file: {filename}")
    try:
        static_path = os.path.join('static', filename)
        print(f"Static path: {static_path}")
        print(f"Static exists: {os.path.exists(static_path)}")
        
        if os.path.exists(static_path):
            from flask import send_file
            
            # Determine proper MIME type
            ext = filename.lower().split('.')[-1]
            mime_types = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'svg': 'image/svg+xml',
                'webp': 'image/webp',
                'css': 'text/css',
                'js': 'application/javascript',
                'json': 'application/json',
                'txt': 'text/plain',
                'html': 'text/html'
            }
            mimetype = mime_types.get(ext, 'application/octet-stream')
            
            response = send_file(
                static_path,
                mimetype=mimetype,
                as_attachment=False
            )
            # Set cache headers manually
            response.cache_control.max_age = 31536000  # 1 year cache
            return response
        else:
            print(f"Static file not found: {static_path}")
            return "File not found", 404
    except Exception as e:
        print(f"Error serving static file {filename}: {str(e)}")
        return "Error serving static file", 500

@app.route('/debug/static')
@app.route('/daily/debug/static')
def debug_static():
    """Debug route to check static files and URL generation"""
    try:
        import os
        debug_info = {
            'current_directory': os.getcwd(),
            'static_exists': os.path.exists('static'),
            'logos_exists': os.path.exists('static/logos'),
            'static_url_prefix': STATIC_URL_PREFIX,
            'app_base_url': APP_BASE_URL,
            'environment': ENVIRONMENT,
            'application_root': app.config.get('APPLICATION_ROOT', 'Not set'),
            'sample_logo_url': generate_static_url('logos/sample.png'),
            'sample_static_url': generate_static_url('image.jpeg'),
            'test_urls': {
                'logo_dev': '/static/logos/sample.png',
                'logo_prod': '/daily/static/logos/sample.png',
                'static_dev': '/static/image.jpeg',
                'static_prod': '/daily/static/image.jpeg'
            }
        }
        
        if os.path.exists('static'):
            debug_info['static_files'] = os.listdir('static')
        
        if os.path.exists('static/logos'):
            debug_info['logo_files'] = os.listdir('static/logos')
            # Test with actual logo file if exists
            if debug_info['logo_files']:
                actual_logo = debug_info['logo_files'][0]
                debug_info['actual_logo_url'] = generate_static_url(f'logos/{actual_logo}')
                debug_info['test_urls']['actual_logo_dev'] = f'/static/logos/{actual_logo}'
                debug_info['test_urls']['actual_logo_prod'] = f'/daily/static/logos/{actual_logo}'
            
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
                        logo_url = f"{STATIC_URL_PREFIX}/static/logos/{logo_filename}"
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
        template_name = request.form.get('template', 'report_template.html')
        show_interactions = 'false'  # Default value
        
        print(f"=== Form Parameters Debug ===")
        print(f"Request method: {request.method}")
        print(f"Content-Type: {request.content_type}")
        print(f"All form keys: {list(request.form.keys())}")
        print(f"All files keys: {list(request.files.keys())}")
        for key, value in request.form.items():
            print(f"  {key}: '{value}' (type: {type(value)})")
        print(f"Raw template value from form: '{request.form.get('template')}'")
        print(f"Template with default: '{request.form.get('template', 'DEFAULT_FALLBACK')}'")
        print(f"=============================")
        
        print(f"Parameters: brand_name={brand_name}, report_name={report_name}, report_date={report_date}, template={template_name}")
        
        if not brand_name or not report_name or not report_date:
            print("Error: Missing required parameters")
            return jsonify({'error': 'Brand name, report name and report date are required'}), 400
        
        # Validate template name for security
        allowed_templates = [
            'report_template.html',
            'report_template_aurora.html', 
            'report_template_clarity.html',
            'report_template_dark.html'
        ]
        original_template = template_name
        if template_name not in allowed_templates:
            print(f"Invalid template: {template_name}, using default")
            template_name = 'report_template.html'
        else:
            print(f"Template validation passed: {template_name}")
        
        print(f"Final template to use: {template_name} (original: {original_template})")
        
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
        
        # Add static_url_prefix to template context
        api_data['static_url_prefix'] = STATIC_URL_PREFIX
        
        # Render the template with API data
        try:
            print(f"Template folder: {app.template_folder}")
            print(f"Looking for template: {template_name}")
            template_path = os.path.join(app.template_folder, template_name)
            print(f"Full template path: {template_path}")
            print(f"Template exists: {os.path.exists(template_path)}")
            
            # Fallback to default template if selected template doesn't exist
            if not os.path.exists(template_path):
                print(f"Template {template_name} not found, falling back to default")
                template_name = 'report_template.html'
                template_path = os.path.join(app.template_folder, template_name)
                print(f"Fallback template path: {template_path}")
                print(f"Fallback template exists: {os.path.exists(template_path)}")
            
            html_content = render_template(template_name, **api_data)
            print(f"Template {template_name} rendered successfully")
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
            'path': report_path,
            'template_used': template_name
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
        # Get template parameter from query string
        template_name = request.args.get('template', 'report_template.html')
        
        # Load data from JSON file
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Generate HTML report using template
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        brand_slug = data['report_metadata']['brand'].lower().replace(' ', '-').replace('ă', 'a').replace('ầ', 'au')
        filename = f"{brand_slug}-{timestamp}.html"
        
        # Add static_url_prefix to template context
        data['static_url_prefix'] = STATIC_URL_PREFIX
        
        # Render the selected template with data
        try:
            print(f"Template folder: {app.template_folder}")
            print(f"Looking for template: {template_name}")
            template_path = os.path.join(app.template_folder, template_name)
            print(f"Full template path: {template_path}")
            print(f"Template exists: {os.path.exists(template_path)}")
            
            # Fallback to default template if selected template doesn't exist
            if not os.path.exists(template_path):
                print(f"Template {template_name} not found, falling back to default")
                template_name = 'report_template.html'
                template_path = os.path.join(app.template_folder, template_name)
                print(f"Fallback template path: {template_path}")
                print(f"Fallback template exists: {os.path.exists(template_path)}")
            
            html_content = render_template(template_name, **data)
            print(f"Template {template_name} rendered successfully")
        except Exception as e:
            print(f"Template rendering error: {str(e)}")
            return jsonify({'error': f'Error generating report template: {str(e)}'}), 500
        
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
            'path': report_path,
            'template_used': template_name
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
        
        # Add static_url_prefix to template context
        data['static_url_prefix'] = STATIC_URL_PREFIX
        
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

@app.route('/api/test-form', methods=['POST'])
def test_form():
    """Test form submission to debug template parameter"""
    try:
        print("=== Test Form Submission ===")
        print(f"Content-Type: {request.content_type}")
        print(f"Form keys: {list(request.form.keys())}")
        print(f"Files keys: {list(request.files.keys())}")
        
        form_data = {}
        for key, value in request.form.items():
            form_data[key] = value
            print(f"  {key}: {value}")
        
        template_param = request.form.get('template', 'NOT_FOUND')
        print(f"Template parameter: '{template_param}'")
        
        return jsonify({
            'success': True,
            'form_data': form_data,
            'template_param': template_param,
            'all_keys': list(request.form.keys())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates')
@app.route('/daily/api/templates')
def list_templates():
    """List available templates for debugging"""
    try:
        template_dir = app.template_folder
        print(f"Template directory: {template_dir}")
        
        if not os.path.exists(template_dir):
            return jsonify({'error': f'Template directory does not exist: {template_dir}'}), 404
        
        templates = []
        for file in os.listdir(template_dir):
            if file.endswith('.html') and file.startswith('report_template'):
                file_path = os.path.join(template_dir, file)
                templates.append({
                    'name': file,
                    'path': file_path,
                    'exists': os.path.exists(file_path),
                    'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
                })
        
        return jsonify({
            'template_folder': template_dir,
            'templates': templates,
            'total_templates': len(templates)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/<filename>', methods=['DELETE'])
@app.route('/daily/api/reports/<filename>', methods=['DELETE'])
def delete_report(filename):
    """Delete a specific report file"""
    try:
        # Validate filename to prevent directory traversal
        if not filename.endswith('.html') or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        file_path = os.path.join(REPORTS_DIR, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({'error': 'Report not found'}), 404
        
        # Delete the file
        os.remove(file_path)
        print(f"Report deleted: {file_path}")
        
        return jsonify({
            'success': True,
            'message': f'Report {filename} deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting report: {str(e)}")
        return jsonify({'error': f'Failed to delete report: {str(e)}'}), 500

@app.route('/api/reports')
@app.route('/daily/api/reports')
def list_reports():
    files = os.listdir(REPORTS_DIR)
    reports = []
    for f in files:
        if f.endswith('.html'):
            url = f"/report/{f}"
            # Generate full URL using environment variable
            if APP_BASE_URL and APP_BASE_URL != 'http://localhost:8000':
                full_url = f"{APP_BASE_URL}{url}"
            else:
                host = request.host.replace('0.0.0.0', 'localhost')
                full_url = f"http://{host}{url}"
            
            reports.append({
                'filename': f, 
                'url': url,
                'full_url': full_url
            })
    return jsonify(reports)

if __name__ == '__main__':
    print(f"Starting server on {HOST}:{PORT}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"App Base URL: {APP_BASE_URL}")
    print(f"Debug mode: {DEBUG}")
    print(f"Template folder: {app.template_folder}")
    
    # Check if template files exist
    required_templates = [
        'report_template.html',
        'report_template_aurora.html', 
        'report_template_clarity.html',
        'report_template_dark.html'
    ]
    
    print("\n=== Template Check ===")
    for template in required_templates:
        template_path = os.path.join(app.template_folder, template)
        exists = os.path.exists(template_path)
        print(f"{template}: {'✓' if exists else '✗'} ({template_path})")
        if not exists:
            print(f"WARNING: Template {template} not found!")
    
    print("======================\n")
    
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)