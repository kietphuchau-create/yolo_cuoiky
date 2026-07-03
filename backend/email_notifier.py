# backend/email_notifier.py
# Module gửi cảnh báo phát hiện vật thể qua Gmail sử dụng SMTP_SSL

import time
import threading
import cv2
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

from config import logger

# ============================================================
# Cấu hình Gmail (cập nhật qua API /api/email/config)
# ============================================================
email_config = {
    'sender_email': 'taigame6371@gmail.com',
    'app_password': 'rjsq lcxj ydyp dyko',    # Mật khẩu ứng dụng 16 ký tự của Google
    'receiver_email': 'taigame6371@gmail.com',
    'enabled': True,
    'cooldown': 60,        # Giây tối thiểu giữa các lần gửi mail (mặc định 60s)
    'min_objects': 1,      # Số vật thể tối thiểu để gửi mail
}

_last_sent_time = 0        # Timestamp lần gửi mail cuối cùng
_send_lock = threading.Lock()


def _is_configured():
    """Kiểm tra cấu hình Gmail đã đầy đủ chưa."""
    return (
        email_config['enabled']
        and email_config['sender_email'].strip()
        and email_config['app_password'].strip()
        and email_config['receiver_email'].strip()
    )


def _can_send():
    """Kiểm tra cooldown tránh spam hòm thư."""
    global _last_sent_time
    now = time.time()
    return (now - _last_sent_time) >= email_config['cooldown']


def _build_html_body(counts, source="Camera trực tiếp"):
    """Tạo nội dung HTML cho email cảnh báo."""
    now_str = datetime.now().strftime('%H:%M:%S — %d/%m/%Y')
    total = sum(counts.values())

    rows = ""
    for name, count in sorted(counts.items(), key=lambda x: -x[1]):
        rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; text-transform: capitalize;">{name}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: bold; color: #2563eb;">{count}</td>
        </tr>
        """

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
        <h2 style="color: #ef4444; border-bottom: 2px solid #ef4444; padding-bottom: 10px; margin-top: 0;">
            ⚠️ YOLO Vision — Cảnh báo phát hiện vật thể!
        </h2>
        <p>Hệ thống vừa phát hiện các vật thể sau từ nguồn: <strong>{source}</strong></p>
        
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
            <thead>
                <tr style="background-color: #f3f4f6;">
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Tên vật thể</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center; width: 100px;">Số lượng</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        
        <p style="margin-bottom: 5px;">⏰ <strong>Thời gian:</strong> {now_str}</p>
        <p>📷 <em>Ảnh chụp nhận diện thực tế được đính kèm ở dưới thư này.</em></p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 0.85em; color: #888; text-align: center;">Đây là email tự động gửi từ hệ thống YOLO Vision Object Detection.</p>
    </body>
    </html>
    """
    return html


def send_email_alert(frame, counts, source="Camera trực tiếp", force_send=False):
    """
    Gửi email cảnh báo kèm ảnh chụp annotated.
    Chạy bất đồng bộ trên thread riêng để không block luồng xử lý chính.
    """
    if force_send:
        if (not email_config['sender_email'].strip() 
                or not email_config['app_password'].strip() 
                or not email_config['receiver_email'].strip()):
            return False
    else:
        if not _is_configured():
            return False

    if not counts or sum(counts.values()) < email_config['min_objects']:
        return False

    if not force_send:
        with _send_lock:
            if not _can_send():
                return False
            global _last_sent_time
            _last_sent_time = time.time()

    # Chạy trên background thread riêng
    thread = threading.Thread(
        target=_do_send_email,
        args=(frame.copy(), counts, source),
        daemon=True
    )
    thread.start()
    return True


def _do_send_email(frame, counts, source):
    """Thực thi gửi email (Background thread)."""
    try:
        sender = email_config['sender_email']
        password = email_config['app_password']
        receiver = email_config['receiver_email']

        # Tạo MIME Message
        msg = MIMEMultipart('related')
        msg['Subject'] = f"⚠️ YOLO Vision: Phát hiện {sum(counts.values())} vật thể từ {source}"
        msg['From'] = f"YOLO Vision Alerts <{sender}>"
        msg['To'] = receiver

        # Encode frame thành JPEG bytes
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            logger.warning("Gmail: Không thể encode ảnh.")
            return

        # HTML body
        html_content = _build_html_body(counts, source)
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        
        # Attach HTML
        msg_text = MIMEText(html_content, 'html')
        msg_alternative.attach(msg_text)

        # Đính kèm ảnh JPEG
        img_data = buffer.tobytes()
        msg_image = MIMEImage(img_data, name="detection.jpg")
        msg_image.add_header('Content-ID', '<detection_image>')
        msg_image.add_header('Content-Disposition', 'inline', filename="detection.jpg")
        msg.attach(msg_image)

        # Gửi SMTP SSL qua cổng 465 của Google
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
            
        logger.info(f"Gmail: Đã gửi email cảnh báo thành công tới {receiver}")

    except Exception as e:
        logger.error(f"Gmail: Lỗi gửi email cảnh báo: {e}")


def send_email_message(subject, text_body):
    """Gửi email văn bản thuần (dùng để test kết nối)."""
    sender = email_config['sender_email']
    password = email_config['app_password']
    receiver = email_config['receiver_email']

    if not sender or not password or not receiver:
        return False

    try:
        msg = MIMEText(text_body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = f"YOLO Vision <{sender}>"
        msg['To'] = receiver

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Gmail: Lỗi gửi email test: {e}")
        return False


def test_email_connection():
    """Gửi email test để xác minh cấu hình."""
    now_str = datetime.now().strftime('%H:%M:%S — %d/%m/%Y')
    subject = "✅ YOLO Vision — Kết nối Gmail thành công!"
    body = (
        "Xin chào,\n\n"
        "Đây là email kiểm tra kết nối từ ứng dụng YOLO Vision Object Detection.\n"
        "Hệ thống SMTP Gmail của bạn đã được kết nối và xác thực thành công!\n\n"
        f"⏰ Thời gian gửi: {now_str}\n"
        f"🔔 Cooldown mặc định: {email_config['cooldown']} giây\n"
        f"📊 Số lượng vật thể tối thiểu gửi cảnh báo: {email_config['min_objects']} vật thể.\n\n"
        "Chúc bạn một ngày làm việc hiệu quả!"
    )
    return send_email_message(subject, body)
