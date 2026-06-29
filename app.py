from technical import init_technical_tables
from gd_realtime import gd_realtime_bp
from hr_realtime import hr_realtime_bp
from enhanced_api_routes import enhanced_api_bp
from api_routes import api_bp
from feedback import feedback_bp
from hr import hr_bp
from gd import gd_bp
from technical import technical_bp
from aptitude_routes import aptitude_bp, init_aptitude_tables
from database import init_db
from dashboard import dashboard_bp
from routes import routes_bp
from auth import auth_bp, init_oauth
from flask import Flask, jsonify, render_template
from flask_cors import CORS
import os
import nltk
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import blueprints

app = Flask(__name__, template_folder="templates")

# Load configuration based on environment
if os.getenv("FLASK_ENV") == "production":
    from config import ProductionConfig
    app.config.from_object(ProductionConfig)
    logger.info("Loaded production configuration")
else:
    # Development configuration
    app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key_change_in_production")
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['UPLOAD_FOLDER'] = 'uploads'
    logger.info("Loaded development configuration")

# CORS Configuration
cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5000").split(",")
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# Application startup time for metrics
app.start_time = time.time()

# Ensure NLTK resources are available
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    logger.info("Downloading NLTK punkt tokenizer...")
    nltk.download("punkt", quiet=True)

try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    logger.info("Downloading NLTK punkt_tab tokenizer...")
    nltk.download("punkt_tab", quiet=True)

# Download other commonly needed NLTK resources
try:
    nltk.download("stopwords", quiet=True)
    nltk.download("vader_lexicon", quiet=True)
    nltk.download("averaged_perceptron_tagger", quiet=True)
    nltk.download("averaged_perceptron_tagger_eng", quiet=True)
except Exception as e:
    logger.warning(f"Could not download some NLTK resources: {e}")

# Initialize Database
init_db()
init_aptitude_tables()

# Initialize technical tables
init_technical_tables()

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(routes_bp)
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(aptitude_bp)
app.register_blueprint(technical_bp)
app.register_blueprint(gd_bp)
app.register_blueprint(hr_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(api_bp)
app.register_blueprint(enhanced_api_bp)
app.register_blueprint(hr_realtime_bp)  # Real-time video interview
app.register_blueprint(gd_realtime_bp)  # Real-time group discussion

# Initialize OAuth (optional)
try:
    init_oauth(app)
    logger.info("Google OAuth initialized successfully")
except FileNotFoundError as e:
    logger.warning(f"client_secret.json not found; Google OAuth disabled: {e}")
except Exception as e:
    logger.warning(f"OAuth initialization failed; Google OAuth disabled: {e}")

# Health and Metrics Endpoints


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "AI-Powered Virtual Interviewer"
    }), 200


@app.route("/metrics")
def metrics():
    """Service metrics endpoint"""
    uptime = time.time() - app.start_time
    return jsonify({
        "uptime_seconds": round(uptime, 2),
        "uptime_minutes": round(uptime / 60, 2),
        "service": "AI-Powered Virtual Interviewer",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }), 200

# 🔹 Default route -> Render the homepage


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return "", 204

# Error Handlers


@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"success": False, "error": "Internal server error"}), 500


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"success": False, "error": "Bad request"}), 400


if __name__ == "__main__":
    print("AI-Powered Virtual Interviewer - API")
    print("Server starting on http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
