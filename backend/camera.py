# backend/camera.py
# Class CameraStream và các hàm quản lý camera

import cv2
import threading
import time
import os
import atexit

from config import model_lock, logger, CONF_THRESHOLD, FRAME_WIDTH, FRAME_HEIGHT


class CameraStream:
    def __init__(self, src=0, model=None, save_dir=None):
        self.src = src
        self.model = model
        self.save_dir = save_dir
        
        self.grabbed = False
        self.frame = None
        self.annotated_frame = None
        
        self.started = False
        self.read_lock = threading.Lock()
        self.thread = None
        self.counts = {}  # Số lượng vật thể đang có mặt trong khung hình
        self.cap = None
        self.connected = False      # True khi camera mở thành công
        self.connect_error = False  # True khi camera không mở được
        
        self.log_file = None
        self.start_time = time.time()
        
        if self.save_dir:
            os.makedirs(self.save_dir, exist_ok=True)
            self.log_file = os.path.join(self.save_dir, "thong_ke_so_luong.txt")
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write("BẢNG THỐNG KÊ SỐ LƯỢNG VẬT THỂ HIỆN CÓ (TRỰC TIẾP)\n")
                f.write("="*50 + "\n")

    def start(self):
        """Start the background thread for frame capture and inference."""
        if self.started:
            return self
        self.started = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()
        return self

    def update(self):
        """Continuously read frames, run YOLO inference, and store annotated frames."""
        import camera as _cam_module  # import module để luôn đọc giá trị mới nhất
        
        if isinstance(self.src, int) or str(self.src).isdigit():
            self.cap = cv2.VideoCapture(int(self.src), cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(self.src)
            
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            self.connected = True
            self.connect_error = False
            logger.info(f"Camera {self.src} opened successfully in background thread.")
        else:
            self.connected = False
            self.connect_error = True
            logger.error(f"Failed to open camera: {self.src} in background thread.")
            
        while self.started:
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.1)
                continue
                
            grabbed, frame = self.cap.read()
            if not grabbed:
                time.sleep(0.01)
                continue
            
            # Chạy suy luận YOLO trực tiếp trên background thread này
            if self.model and _cam_module.live_yolo_active:
                with model_lock:
                    results = self.model.predict(source=frame, conf=0.5, show=False, verbose=False)
                annotated = results[0].plot()
                
                # Đếm số lượng vật thể hiện có trong khung hình
                current_counts = {}
                if len(results) > 0 and len(results[0].boxes) > 0:
                    for box in results[0].boxes:
                        cls_id = int(box.cls[0].item())
                        cls_name = self.model.names[cls_id]
                        current_counts[cls_name] = current_counts.get(cls_name, 0) + 1
                
                # Cập nhật counts = số lượng hiện có (tự động trừ khi vật thể ra khỏi khung)
                # Ghi log nếu có vật thể và có thư mục lưu
                if self.save_dir and self.log_file and current_counts:
                    elapsed = time.time() - self.start_time
                    time_str = time.strftime('%H:%M:%S', time.gmtime(elapsed))
                    log_line = f"[{time_str} - {elapsed:.2f}s] Số lượng hiện có: {current_counts}\n"
                    with open(self.log_file, "a", encoding="utf-8") as f:
                        f.write(log_line)

                # Gửi cảnh báo Telegram (có cooldown tự động)
                if current_counts:
                    try:
                        from telegram_notifier import send_telegram_alert
                        send_telegram_alert(annotated, current_counts, source="Camera trực tiếp")
                    except Exception:
                        pass  # Không để lỗi Telegram ảnh hưởng camera

                    try:
                        from email_notifier import send_email_alert
                        send_email_alert(annotated, current_counts, source="Camera trực tiếp")
                    except Exception:
                        pass  # Không để lỗi Gmail ảnh hưởng camera
            else:
                annotated = frame.copy()
                current_counts = {}
                
            with self.read_lock:
                self.grabbed = grabbed
                self.frame = frame
                self.annotated_frame = annotated
                self.counts = current_counts
                
        if self.cap and self.cap.isOpened():
            self.cap.release()

    def read(self):
        """Thread‑safe retrieval of the latest annotated frame."""
        with self.read_lock:
            if self.annotated_frame is not None:
                return self.grabbed, self.annotated_frame.copy()
            return self.grabbed, None

    def stop(self):
        """Stop the background thread and release the camera resource."""
        self.started = False
        if self.thread:
            self.thread.join(timeout=1.0)


# ============================================================
# Trạng thái camera (module-level variables)
# ============================================================
DEFAULT_CAMERA_URL = 0
current_camera_url = DEFAULT_CAMERA_URL
current_camera_save_dir = None
camera_stream = None
camera_active = False
live_yolo_active = False
stream_lock = threading.Lock()


def get_camera_stream():
    """Lấy instance CameraStream hiện tại."""
    global camera_stream
    return camera_stream


def release_camera_stream():
    """Giải phóng camera stream (dừng thread + release camera)."""
    global camera_stream
    with stream_lock:
        if camera_stream is not None:
            camera_stream.stop()
            camera_stream = None


# Ensure camera resources are released on process exit
atexit.register(release_camera_stream)


def generate_frames():
    """Generator yielding MJPEG frames từ camera stream."""
    while True:
        stream = get_camera_stream()
        if stream is None:
            time.sleep(0.1)
            continue
            
        success, frame = stream.read()
        if not success or frame is None:
            time.sleep(0.03)  # Tránh chiếm dụng tài nguyên CPU khi chưa sẵn sàng
            continue
            
        # Chuyển đổi khung hình OpenCV sang định dạng JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        
        # Yield luồng dữ liệu (multipart)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Giới hạn tốc độ gửi để tiết kiệm băng thông mạng (~30 FPS)
        time.sleep(0.03)
