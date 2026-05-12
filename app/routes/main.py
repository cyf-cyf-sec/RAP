from flask import Blueprint, render_template, request, jsonify
import requests
from urllib.parse import urlparse
from ..utils.error_handling import (
    error_handler, validate_required_fields, validate_github_url, 
    RepositoryError, ValidationError
)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@error_handler
def index():
    """Homepage - Display repository input form"""
    return render_template('index.html')

@main_bp.route('/submit-analysis', methods=['POST'])
@error_handler
def submit_analysis():
    """Handle form submission and start analysis"""
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
    
    if not data:
        raise ValidationError('Invalid request data')

    validate_required_fields(data, ['repo_url'])

    repo_url = data['repo_url'].strip()
    validate_github_url(repo_url)

    return jsonify({
        'success': True,
        'message': 'Analysis task submitted',
        'task_id': 'temp_task_id'
    })

@main_bp.route('/api/validate-repository', methods=['POST'])
@error_handler
def validate_repository():
    """Validate repository accessibility with provided token"""
    data = request.get_json()
    
    if not data:
        raise ValidationError('Invalid request data')
    
    repo_url = data.get('repo_url', '').strip()
    github_token = data.get('github_token', '').strip()
    
    if not repo_url:
        raise ValidationError('Repository URL cannot be empty')
    
    validate_github_url(repo_url)

    repo_info = extract_repo_info(repo_url)
    if not repo_info:
        raise ValidationError('Failed to parse repository information')

    is_valid, error_message = validate_repo_accessibility(repo_info, github_token)
    
    if is_valid:
        return jsonify({
            'valid': True,
            'message': 'Repository connection validated successfully',
            'repo_info': repo_info
        })
    else:
        raise RepositoryError(error_message)

@main_bp.route('/results')
def results():
    """Display analysis results page"""
    task_id = request.args.get('task_id', '')
    return render_template('results.html', task_id=task_id)

def is_valid_github_url(url):
    """Validate if it's a valid GitHub repository URL"""
    try:
        parsed = urlparse(url)
        if parsed.netloc != 'github.com':
            return False
        
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) < 2:
            return False
        
        return True
    except:
        return False

def extract_repo_info(repo_url):
    """Extract repository information from URL"""
    try:
        parsed = urlparse(repo_url)
        path_parts = parsed.path.strip('/').split('/')
        
        if len(path_parts) >= 2:
            return {
                'owner': path_parts[0],
                'repo': path_parts[1],
                'full_name': f'{path_parts[0]}/{path_parts[1]}'
            }
        return None
    except:
        return None

def validate_repo_accessibility(repo_info, token):
    """Validate repository accessibility"""
    try:
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if token:
            headers['Authorization'] = f'token {token}'
        
        api_url = f'https://api.github.com/repos/{repo_info["full_name"]}'
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return True, None
        elif response.status_code == 404:
            return False, 'Repository does not exist or is inaccessible'
        elif response.status_code == 401:
            return False, 'Invalid token or insufficient permissions'
        elif response.status_code == 403:
            rate_limit_response = requests.get('https://api.github.com/rate_limit', headers=headers)
            if rate_limit_response.status_code == 200:
                rate_data = rate_limit_response.json()
                if rate_data['resources']['core']['remaining'] == 0:
                    return False, 'API request limit reached'
            return False, 'Access denied, possibly permission issue'
        else:
            return False, f'GitHub API error: {response.status_code}'
            
    except requests.exceptions.Timeout:
        return False, 'Connection to GitHub timed out'
    except requests.exceptions.ConnectionError:
        return False, 'Network connection error'
    except Exception as e:
        return False, f'Error during validation: {str(e)}'