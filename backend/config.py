# backend/config.py
# Cấu hình chung và shared state cho toàn bộ ứng dụng

import os
import threading
import logging
from ultralytics import YOLO

# ============================================================
# Logging
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
)
logger = logging.getLogger(__name__)

# ============================================================
# Đường dẫn
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MODEL_PATH = os.path.join(BASE_DIR, '..', 'models', 'best_Day_du.pt')

# ============================================================
# Cấu hình YOLO
# ============================================================
CONF_THRESHOLD = float(os.getenv('YOLO_CONF_THRESHOLD', '0.5'))
FRAME_WIDTH = int(os.getenv('FRAME_WIDTH', '640'))
FRAME_HEIGHT = int(os.getenv('FRAME_HEIGHT', '480'))

# ============================================================
# Tải mô hình YOLO
# ============================================================
try:
    model = YOLO(MODEL_PATH)
    logger.info(f"Đã tải mô hình từ {MODEL_PATH} thành công!")
except Exception as e:
    logger.error(f"Lỗi khi tải mô hình: {e}")
    model = None

# ============================================================
# Shared State
# ============================================================
model_lock = threading.Lock()   # Lock khi sử dụng model (thread-safe)
video_tasks = {}                # Lưu trạng thái các task quét video

# ============================================================
# Telegram (cấu hình mặc định)
# ============================================================
TELEGRAM_COOLDOWN = int(os.getenv('TELEGRAM_COOLDOWN', '30'))  # Giây giữa các lần gửi

