# backend/routes/telegram_routes.py
# Routes: /api/telegram/config (GET, POST), /api/telegram/test (POST)

from flask import Blueprint, request, jsonify

from telegram_notifier import telegram_config, test_telegram_connection
from config import logger

telegram_bp = Blueprint('telegram', __name__)


@telegram_bp.route('/api/telegram/config', methods=['GET'])
def get_telegram_config():
    """Lấy cấu hình Telegram hiện tại (ẩn token)."""
    safe_config = telegram_config.copy()
    # Ẩn token — chỉ hiện 8 ký tự cuối
    token = safe_config.get('bot_token', '')
    if len(token) > 8:
        safe_config['bot_token_masked'] = '***' + token[-8:]
    else:
        safe_config['bot_token_masked'] = token
    safe_config.pop('bot_token', None)

    return jsonify({"status": "success", "config": safe_config})


@telegram_bp.route('/api/telegram/config', methods=['POST'])
def update_telegram_config():
    """Cập nhật cấu hình Telegram."""
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Dữ liệu không hợp lệ."})

    if 'bot_token' in data:
        telegram_config['bot_token'] = data['bot_token'].strip()
    if 'chat_id' in data:
        telegram_config['chat_id'] = str(data['chat_id']).strip()
    if 'enabled' in data:
        telegram_config['enabled'] = bool(data['enabled'])
    if 'cooldown' in data:
        cooldown = int(data['cooldown'])
        telegram_config['cooldown'] = max(5, min(cooldown, 300))  # 5s — 5 phút
    if 'min_objects' in data:
        min_obj = int(data['min_objects'])
        telegram_config['min_objects'] = max(1, min(min_obj, 50))

    logger.info(f"Telegram config updated: enabled={telegram_config['enabled']}, "
                f"chat_id={telegram_config['chat_id']}, "
                f"cooldown={telegram_config['cooldown']}s")

    return jsonify({"status": "success", "message": "Đã cập nhật cấu hình Telegram."})


@telegram_bp.route('/api/telegram/test', methods=['POST'])
def test_telegram():
    """Gửi tin nhắn test để kiểm tra kết nối bot."""
    if not telegram_config['bot_token'] or not telegram_config['chat_id']:
        return jsonify({"status": "error", "message": "Chưa nhập Bot Token hoặc Chat ID."})

    success = test_telegram_connection()
    if success:
        return jsonify({"status": "success", "message": "Đã gửi tin nhắn test! Kiểm tra Telegram."})
    else:
        return jsonify({"status": "error", "message": "Gửi thất bại. Kiểm tra lại Token và Chat ID."})
