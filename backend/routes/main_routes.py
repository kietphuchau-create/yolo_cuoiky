# backend/routes/main_routes.py
# Routes: / (trang chủ), /health (health check)

from flask import Blueprint, render_template, jsonify

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/health')
def health():
    """Simple health check endpoint."""
    return jsonify(status='ok')
