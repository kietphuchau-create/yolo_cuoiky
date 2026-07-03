# backend/routes/email_routes.py
# Routes: /api/email/config (GET, POST), /api/email/test (POST)

from flask import Blueprint, request, jsonify

from email_notifier import email_config, test_email_connection
from config import logger

email_bp = Blueprint('email', __name__)


@email_bp.route('/api/email/config', methods=['GET'])
def get_email_config():
    """Lấy cấu hình Gmail hiện tại (ẩn mật khẩu ứng dụng)."""
    safe_config = email_config.copy()
    pw = safe_config.get('app_password', '')
    if len(pw) > 4:
        safe_config['app_password_masked'] = '***' + pw[-4:]
    else:
        safe_config['app_password_masked'] = pw
    safe_config.pop('app_password', None)

    return jsonify({"status": "success", "config": safe_config})


@email_bp.route('/api/email/config', methods=['POST'])
def update_email_config():
    """Cập nhật cấu hình Gmail."""
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Dữ liệu không hợp lệ."})

    if 'sender_email' in data:
        email_config['sender_email'] = data['sender_email'].strip()
    if 'app_password' in data:
        email_config['app_password'] = data['app_password'].strip()
    if 'receiver_email' in data:
        email_config['receiver_email'] = data['receiver_email'].strip()
    if 'enabled' in data:
        email_config['enabled'] = bool(data['enabled'])
    if 'cooldown' in data:
        cooldown = int(data['cooldown'])
        email_config['cooldown'] = max(5, min(cooldown, 3600))  # 5s — 1 tiếng
    if 'min_objects' in data:
        min_obj = int(data['min_objects'])
        email_config['min_objects'] = max(1, min(min_obj, 50))

    logger.info(f"Gmail config updated: enabled={email_config['enabled']}, "
                f"sender={email_config['sender_email']}, "
                f"receiver={email_config['receiver_email']}, "
                f"cooldown={email_config['cooldown']}s")

    return jsonify({"status": "success", "message": "Đã cập nhật cấu hình Gmail thành công."})


@email_bp.route('/api/email/test', methods=['POST'])
def test_email():
    """Gửi email test để kiểm tra cấu hình SMTP."""
    if not email_config['sender_email'] or not email_config['app_password'] or not email_config['receiver_email']:
        return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ email gửi, mật khẩu ứng dụng và email nhận."})

    success = test_email_connection()
    if success:
        return jsonify({"status": "success", "message": "Đã gửi email test thành công! Hãy kiểm tra hộp thư nhận."})
    else:
        return jsonify({"status": "error", "message": "Gửi email thất bại. Hãy kiểm tra lại email gửi, mật khẩu ứng dụng và kết nối."})
