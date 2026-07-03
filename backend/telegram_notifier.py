# backend/telegram_notifier.py
# Module gửi cảnh báo phát hiện vật thể qua Telegram Bot API

import time
import threading
import cv2
import requests
from datetime import datetime

from config import logger

# ============================================================
# Cấu hình Telegram (cập nhật qua API /api/telegram/config)
# ============================================================
telegram_config = {
    'bot_token': '8748656188:AAGthg13ZJFf3H3oVo_aCY3LMNDFneq1-ao',
    'chat_id': '6090629286',
    'enabled': True,
    'cooldown': 30,       # Giây tối thiểu giữa các lần gửi
    'min_objects': 1,     # Số vật thể tối thiểu để kích hoạt cảnh báo
}

_last_sent_time = 0       # Timestamp lần gửi cuối cùng
_send_lock = threading.Lock()


def _is_configured():
    """Kiểm tra đã cấu hình đầy đủ chưa."""
    return (
        telegram_config['enabled']
        and telegram_config['bot_token'].strip()
        and telegram_config['chat_id'].strip()
    )


def _can_send():
    """Kiểm tra cooldown — tránh gửi spam."""
    global _last_sent_time
    now = time.time()
    return (now - _last_sent_time) >= telegram_config['cooldown']


def _build_caption(counts, source="Camera trực tiếp"):
    """Tạo nội dung caption cho ảnh cảnh báo."""
    now_str = datetime.now().strftime('%H:%M:%S — %d/%m/%Y')
    total = sum(counts.values())

    lines = [
        "⚠️ *CẢNH BÁO AI: Phát hiện vật thể!*",
        "",
        f"📋 *Thống kê ({total} vật thể):*",
    ]
    for name, count in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"  • {name}: *{count}*")

    lines.append("")
    lines.append(f"⏰ Thời gian: `{now_str}`")
    lines.append(f"📷 Nguồn: {source}")

    return "\n".join(lines)


def send_telegram_alert(frame, counts, source="Camera trực tiếp", force_send=False):
    """
    Gửi ảnh annotated + thống kê vào Telegram.
    Chạy trên thread riêng để không block luồng chính.
    Có cơ chế cooldown để tránh spam.
    """
    if force_send:
        if not telegram_config['bot_token'].strip() or not telegram_config['chat_id'].strip():
            return False
    else:
        if not _is_configured():
            return False

    if not counts or sum(counts.values()) < telegram_config['min_objects']:
        return False

    if not force_send:
        with _send_lock:
            if not _can_send():
                return False
            global _last_sent_time
            _last_sent_time = time.time()

    # Gửi trên thread riêng để không block camera stream
    thread = threading.Thread(
        target=_do_send_photo,
        args=(frame.copy(), counts, source),
        daemon=True
    )
    thread.start()
    return True


def _do_send_photo(frame, counts, source):
    """Thực hiện gửi ảnh (chạy trên background thread)."""
    try:
        token = telegram_config['bot_token']
        chat_id = telegram_config['chat_id']

        # Encode frame thành JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            logger.warning("Telegram: Không thể encode ảnh.")
            return

        caption = _build_caption(counts, source)

        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        files = {'photo': ('detection.jpg', buffer.tobytes(), 'image/jpeg')}
        data = {
            'chat_id': chat_id,
            'caption': caption,
            'parse_mode': 'Markdown',
        }

        resp = requests.post(url, files=files, data=data, timeout=10)

        if resp.status_code == 200:
            logger.info(f"Telegram: Đã gửi cảnh báo — {sum(counts.values())} vật thể.")
        else:
            logger.warning(f"Telegram: Lỗi gửi — {resp.status_code}: {resp.text}")

    except Exception as e:
        logger.error(f"Telegram: Lỗi khi gửi cảnh báo: {e}")


def send_telegram_message(text):
    """Gửi tin nhắn text thuần vào Telegram."""
    if not telegram_config['bot_token'] or not telegram_config['chat_id']:
        return False

    try:
        token = telegram_config['bot_token']
        chat_id = telegram_config['chat_id']

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
        }

        resp = requests.post(url, data=data, timeout=10)
        return resp.status_code == 200

    except Exception as e:
        logger.error(f"Telegram: Lỗi khi gửi tin nhắn: {e}")
        return False


def test_telegram_connection():
    """Gửi tin nhắn test để kiểm tra kết nối bot."""
    now_str = datetime.now().strftime('%H:%M:%S — %d/%m/%Y')
    text = (
        "✅ *YOLO Vision — Kết nối thành công!*\n\n"
        f"🤖 Bot đã sẵn sàng nhận cảnh báo.\n"
        f"⏰ Thời gian: `{now_str}`\n"
        f"🔔 Cooldown: {telegram_config['cooldown']}s\n"
        f"📊 Gửi khi phát hiện ≥ {telegram_config['min_objects']} vật thể"
    )
    return send_telegram_message(text)
