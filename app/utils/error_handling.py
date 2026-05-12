from functools import wraps
from flask import jsonify, current_app
import traceback

class ErrorCode:
    """Error code definitions"""
    # General errors
    VALIDATION_ERROR = 1001
    AUTHENTICATION_ERROR = 1002
    PERMISSION_ERROR = 1003
    RESOURCE_NOT_FOUND = 1004
    RATE_LIMIT_EXCEEDED = 1005
    
    # Business logic errors
    REPOSITORY_NOT_FOUND = 2001
    REPOSITORY_ACCESS_DENIED = 2002
    INVALID_REPOSITORY_URL = 2003
    ANALYSIS_TASK_FAILED = 2004
    
    # System errors
    INTERNAL_SERVER_ERROR = 5001
    EXTERNAL_SERVICE_ERROR = 5002
    DATABASE_ERROR = 5003

class AppError(Exception):
    """Application custom exception base class"""
    
    def __init__(self, message, error_code=None, details=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or ErrorCode.INTERNAL_SERVER_ERROR
        self.details = details

class ValidationError(AppError):
    """Validation error"""
    def __init__(self, message, details=None):
        super().__init__(message, ErrorCode.VALIDATION_ERROR, details)

class RepositoryError(AppError):
    """Repository related errors"""
    def __init__(self, message, error_code=None, details=None):
        super().__init__(message, error_code or ErrorCode.REPOSITORY_ACCESS_DENIED, details)

class ExternalServiceError(AppError):
    """External service error"""
    def __init__(self, message, details=None):
        super().__init__(message, ErrorCode.EXTERNAL_SERVICE_ERROR, details)

def create_error_response(error, include_details=False):
    """Create standardized error response"""
    
    if isinstance(error, AppError):
        response_data = {
            'success': False,
            'error': error.message,
            'error_code': error.error_code
        }
        
        if include_details and error.details:
            response_data['details'] = error.details
    else:
        # Handle non-AppError exceptions
        response_data = {
            'success': False,
            'error': 'Internal server error',
            'error_code': ErrorCode.INTERNAL_SERVER_ERROR
        }
    
    # Set HTTP status code based on error type
    status_code = 500  # Default internal error
    
    if isinstance(error, ValidationError):
        status_code = 400
    elif isinstance(error, (RepositoryError, AppError)):
        if error.error_code == ErrorCode.RESOURCE_NOT_FOUND:
            status_code = 404
        elif error.error_code in [ErrorCode.AUTHENTICATION_ERROR, ErrorCode.PERMISSION_ERROR]:
            status_code = 401
        elif error.error_code == ErrorCode.RATE_LIMIT_EXCEEDED:
            status_code = 429
        else:
            status_code = 400
    
    return jsonify(response_data), status_code

def error_handler(f):
    """Error handling decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # Log error
            current_app.logger.error(f'Error in {f.__name__}: {str(e)}')
            current_app.logger.error(traceback.format_exc())
            
            # Create error response
            return create_error_response(e)
    
    return decorated_function

def validate_required_fields(data, required_fields):
    """Validate required fields"""
    missing_fields = []
    
    for field in required_fields:
        if field not in data or not data[field]:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(
            f'Missing required fields: {", ".join(missing_fields)}',
            details={'missing_fields': missing_fields}
        )

def validate_github_url(url):
    """Validate GitHub repository URL"""
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        if parsed.netloc != 'github.com':
            raise ValidationError('Must be a GitHub repository URL')
        
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) < 2:
            raise ValidationError('Invalid GitHub repository URL format')
        
        return True
    except Exception:
        raise ValidationError('Invalid GitHub repository URL')

def handle_external_service_error(service_name, error):
    """Handle external service errors"""
    if hasattr(error, 'response'):
        status_code = error.response.status_code
        if status_code == 404:
            raise RepositoryError(f'{service_name} service: Resource not found', ErrorCode.RESOURCE_NOT_FOUND)
        elif status_code == 401:
            raise RepositoryError(f'{service_name} service: Authentication failed', ErrorCode.AUTHENTICATION_ERROR)
        elif status_code == 403:
            raise RepositoryError(f'{service_name} service: Permission denied', ErrorCode.PERMISSION_ERROR)
        elif status_code == 429:
            raise RepositoryError(f'{service_name} service: Rate limit exceeded', ErrorCode.RATE_LIMIT_EXCEEDED)
    
    raise ExternalServiceError(f'{service_name} service temporarily unavailable')