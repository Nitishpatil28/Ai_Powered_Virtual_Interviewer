"""
Backend Utility Functions
Centralized utilities for error handling, validation, and common operations
"""

import logging
import json
import os
from typing import Any, Dict, Optional, List
from functools import wraps
from flask import jsonify

# Configure logging
logger = logging.getLogger(__name__)


def setup_logging(app_name: str = "AIInterviewer", level: str = "INFO"):
    """Setup centralized logging configuration"""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log')
        ]
    )

    return logging.getLogger(app_name)


def handle_errors(func):
    """Decorator for consistent error handling in Flask routes"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            logger.error(f"Validation error in {func.__name__}: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 400
        except FileNotFoundError as e:
            logger.error(f"File not found in {func.__name__}: {str(e)}")
            return jsonify({"success": False, "error": "Resource not found"}), 404
        except PermissionError as e:
            logger.error(f"Permission error in {func.__name__}: {str(e)}")
            return jsonify({"success": False, "error": "Permission denied"}), 403
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            return jsonify({"success": False, "error": "Internal server error"}), 500

    return wrapper


def validate_required_fields(data: Dict, required_fields: List[str]) -> Optional[str]:
    """
    Validate that all required fields are present and non-empty

    Args:
        data: Dictionary to validate
        required_fields: List of required field names

    Returns:
        Error message if validation fails, None otherwise
    """
    for field in required_fields:
        if field not in data:
            return f"Missing required field: {field}"
        if not data[field] or (isinstance(data[field], str) and not data[field].strip()):
            return f"Field '{field}' cannot be empty"

    return None


def safe_json_parse(json_str: str, default: Any = None) -> Any:
    """
    Safely parse JSON string with fallback

    Args:
        json_str: JSON string to parse
        default: Default value if parsing fails

    Returns:
        Parsed JSON or default value
    """
    if not json_str:
        return default

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON: {json_str[:100]}")
        # Try to handle Python dict-like strings (single quotes)
        try:
            fixed_str = json_str.replace("'", '"')
            return json.loads(fixed_str)
        except BaseException:
            return default


def safe_json_dumps(data: Any) -> str:
    """
    Safely convert data to JSON string

    Args:
        data: Data to convert

    Returns:
        JSON string
    """
    try:
        return json.dumps(data)
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize to JSON: {str(e)}")
        return "{}"


def create_response(success: bool = True, data: Dict = None, error: str = None,
                    status_code: int = 200) -> tuple:
    """
    Create standardized API response

    Args:
        success: Whether the operation was successful
        data: Response data
        error: Error message if any
        status_code: HTTP status code

    Returns:
        Tuple of (response_dict, status_code)
    """
    response = {"success": success}

    if data:
        response.update(data)

    if error:
        response["error"] = error

    return jsonify(response), status_code


def validate_email(email: str) -> bool:
    """
    Basic email validation

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    import re
    # Remove any directory components
    filename = os.path.basename(filename)
    # Remove any non-alphanumeric characters except dots, underscores, and hyphens
    filename = re.sub(r'[^\w\s.-]', '', filename)
    return filename


def get_env_variable(var_name: str, default: Any = None, required: bool = False) -> Any:
    """
    Get environment variable with optional validation

    Args:
        var_name: Name of environment variable
        default: Default value if not found
        required: Whether the variable is required

    Returns:
        Environment variable value or default

    Raises:
        ValueError: If required variable is not found
    """
    value = os.getenv(var_name, default)

    if required and value is None:
        raise ValueError(f"Required environment variable '{var_name}' is not set")

    return value


def ensure_directory_exists(directory: str) -> None:
    """
    Ensure directory exists, create if it doesn't

    Args:
        directory: Directory path
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Created directory: {directory}")


def log_api_call(endpoint: str, method: str, user_email: str = None,
                 success: bool = True, error: str = None) -> None:
    """
    Log API call for monitoring and debugging

    Args:
        endpoint: API endpoint
        method: HTTP method
        user_email: User making the request
        success: Whether the call was successful
        error: Error message if any
    """
    log_data = {
        "endpoint": endpoint,
        "method": method,
        "user": user_email or "anonymous",
        "success": success
    }

    if error:
        log_data["error"] = error
        logger.error(f"API call failed: {json.dumps(log_data)}")
    else:
        logger.info(f"API call: {json.dumps(log_data)}")


class DatabaseContextManager:
    """Context manager for safe database operations"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        import sqlite3
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.conn.rollback()
            logger.error(f"Database error: {exc_val}")
        else:
            self.conn.commit()

        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()


# Export commonly used functions
__all__ = [
    'setup_logging',
    'handle_errors',
    'validate_required_fields',
    'safe_json_parse',
    'safe_json_dumps',
    'create_response',
    'validate_email',
    'sanitize_filename',
    'get_env_variable',
    'ensure_directory_exists',
    'log_api_call',
    'DatabaseContextManager',
    'logger'
]
