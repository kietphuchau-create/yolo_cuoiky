# backend/app.py
# Entry point — Khởi tạo Flask app và đăng ký tất cả Blueprints

from flask import Flask

# Import config trước để khởi tạo model, logger, v.v.
from config import logger

# Import camera module để đăng ký atexit handler
import camera  # noqa: F401

# Import tất cả Blueprints
from routes.main_routes import main_bp
from routes.camera_routes import camera_bp
from routes.video_routes import video_bp
from routes.image_routes import image_bp
from routes.manage_routes import manage_bp
from routes.telegram_routes import telegram_bp
from routes.email_routes import email_bp

# ============================================================
# Khởi tạo Flask App
# ============================================================
app = Flask(
    __name__,
    template_folder='../frontend/templates',
    static_folder='../frontend/static'
)

# ============================================================
# Đăng ký Blueprints
# ============================================================
app.register_blueprint(main_bp)       # /, /health
app.register_blueprint(camera_bp)     # /video_feed, /api/live_status, /update_camera, ...
app.register_blueprint(video_bp)      # /api/upload_video, /api/scan_existing_video, ...
app.register_blueprint(image_bp)      # /api/scan_image
app.register_blueprint(manage_bp)     # /api/videos, /uploads/<filename>
app.register_blueprint(telegram_bp)   # /api/telegram/config, /api/telegram/test
app.register_blueprint(email_bp)      # /api/email/config, /api/email/test

logger.info("Đã đăng ký tất cả Blueprints thành công!")

# ============================================================
# Chạy Server
# ============================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
