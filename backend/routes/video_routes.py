# backend/routes/video_routes.py
# Routes: /api/upload_video, /api/scan_existing_video, /api/stop_scan/<task_id>,
#          /scan_video_feed/<task_id>, /api/status/<task_id>, /api/check_dir

import os
import time
import shutil
import uuid
import threading

import cv2
from flask import Blueprint, Response, request, jsonify
from werkzeug.utils import secure_filename

from config import model, model_lock, video_tasks, UPLOAD_FOLDER, CONF_THRESHOLD, logger

video_bp = Blueprint('video', __name__)


# ============================================================
# Helper functions (không phải route)
# ============================================================

def process_video_task(task_id, video_path, save_dir, telegram_enabled=False, email_enabled=False):
    try:
        video_tasks[task_id]['status'] = 'processing'
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            total_frames = 100 # fallback
        
        video_tasks[task_id]['total_frames'] = total_frames
        
        log_file = None
        log_buffer = []
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            log_file = os.path.join(save_dir, "thong_ke_so_luong.txt")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("BẢNG THỐNG KÊ SỐ LƯỢNG VẬT THỂ HIỆN CÓ\n")
                f.write("="*50 + "\n")
        
        counts = {}  # Số lượng vật thể hiện có tại frame hiện tại
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30
        
        frame_idx = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_idx += 1
            video_tasks[task_id]['current_frame'] = frame_idx
            
            # Predict
            annotated_frame = frame.copy()
            current_counts = {}  # Đếm số lượng từng class trong frame này
            
            if model:
                with model_lock:
                    results = model.predict(source=frame, conf=CONF_THRESHOLD, show=False, verbose=False)
                annotated_frame = results[0].plot()
                
                # Đếm số lượng vật thể hiện có trong frame
                if len(results) > 0 and len(results[0].boxes) > 0:
                    boxes = results[0].boxes
                    names = model.names
                    
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        cls_name = names[cls_id]
                        current_counts[cls_name] = current_counts.get(cls_name, 0) + 1
            
            # Cập nhật counts = số lượng hiện có (tự động giảm khi vật thể ra khỏi frame)
            counts = current_counts
            
            # Ghi log số lượng hiện có
            if current_counts:
                seconds = frame_idx / fps
                time_str = time.strftime('%H:%M:%S', time.gmtime(seconds))
                if log_file:
                    log_buffer.append(f"[{time_str} - {seconds:.2f}s] Frame {frame_idx}: {current_counts}\n")
                    if len(log_buffer) >= 100:
                        with open(log_file, "a", encoding="utf-8") as f:
                            f.writelines(log_buffer)
                        log_buffer.clear()
                    
                    # Lưu ảnh cho các class được phát hiện
                    for cls_name in current_counts:
                        cls_dir = os.path.join(save_dir, cls_name)
                        os.makedirs(cls_dir, exist_ok=True)
                        frame_name = f"frame_{frame_idx}.jpg"
                        frame_path = os.path.join(cls_dir, frame_name)
                        # Chỉ lưu nếu chưa có (tránh ghi đè liên tục)
                        if not os.path.exists(frame_path):
                            cv2.imwrite(frame_path, annotated_frame)
            
            # Cập nhật frame hiện tại để stream
            ret_img, buffer = cv2.imencode('.jpg', annotated_frame)
            if ret_img:
                video_tasks[task_id]['current_frame_data'] = buffer.tobytes()
            
            # Cập nhật số đếm thống kê trực tiếp ra bên ngoài
            video_tasks[task_id]['counts'] = counts.copy()
                    
            # Sleep 0.03 để stream tầm 30fps
            time.sleep(0.03)
            
            if video_tasks[task_id].get('status') == 'stopped':
                break
            
        cap.release()
        
        # Ghi các log còn dư trong buffer
        if log_file and log_buffer:
            with open(log_file, "a", encoding="utf-8") as f:
                f.writelines(log_buffer)
            log_buffer.clear()
        
        if video_tasks[task_id].get('status') != 'stopped':
            video_tasks[task_id]['status'] = 'completed'
            video_tasks[task_id]['counts'] = counts
            if save_dir:
                video_tasks[task_id]['message'] = f"Đã xử lý xong. Đã lưu ảnh vào {save_dir}"
            else:
                video_tasks[task_id]['message'] = "Đã xử lý xong video."

            # Gửi thông báo Telegram khi quét video xong (nếu được kích hoạt)
            if telegram_enabled and counts:
                try:
                    from telegram_notifier import send_telegram_alert
                    send_telegram_alert(annotated_frame, counts, source="Quét video (hoàn thành)", force_send=True)
                except Exception:
                    pass

            # Gửi email cảnh báo khi quét video xong (nếu được kích hoạt)
            if email_enabled and counts:
                try:
                    from email_notifier import send_email_alert
                    send_email_alert(annotated_frame, counts, source="Quét video (hoàn thành)", force_send=True)
                except Exception:
                    pass
        else:
            video_tasks[task_id]['counts'] = counts
            if save_dir:
                video_tasks[task_id]['message'] = f"Đã dừng quét sớm. Đã lưu ảnh vào {save_dir}"
            else:
                video_tasks[task_id]['message'] = "Đã dừng quét sớm."
        
    except Exception as e:
        logger.error(f"Lỗi khi xử lý video: {e}")
        video_tasks[task_id]['status'] = 'error'
        video_tasks[task_id]['message'] = str(e)


def generate_scan_frames(task_id):
    """Generator yielding frames from the offline video processing task."""
    while True:
        task = video_tasks.get(task_id)
        if not task:
            break
            
        frame_data = task.get('current_frame_data')
        status = task.get('status')
        
        if frame_data:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
                   
        if status in ['completed', 'error', 'stopped']:
            break
            
        time.sleep(0.03)


# ============================================================
# Routes
# ============================================================

@video_bp.route('/api/stop_scan/<task_id>', methods=['POST'])
def stop_scan(task_id):
    if task_id in video_tasks:
        video_tasks[task_id]['status'] = 'stopped'
        return jsonify({"status": "success", "message": "Đã dừng quét video."})
    return jsonify({"status": "error", "message": "Task không tồn tại."})


@video_bp.route('/scan_video_feed/<task_id>')
def scan_video_feed(task_id):
    return Response(generate_scan_frames(task_id), mimetype='multipart/x-mixed-replace; boundary=frame')


@video_bp.route('/api/upload_video', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({"status": "error", "message": "Không tìm thấy file video."})
    
    file = request.files['video']
    local_save_enabled = request.form.get('local_save_enabled', 'false') == 'true'
    telegram_enabled = request.form.get('telegram_enabled', 'false') == 'true'
    email_enabled = request.form.get('email_enabled', 'false') == 'true'
    save_dir = request.form.get('save_dir', '').strip()
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "Tên file rỗng."})
        
    if not local_save_enabled:
        save_dir = None
        
    if local_save_enabled and not save_dir:
        return jsonify({"status": "error", "message": "Chưa nhập thư mục lưu ảnh."})
        
    if save_dir:
        try:
            os.makedirs(save_dir, exist_ok=True)
            # Xóa các file và thư mục cũ trong thư mục nếu có
            for f in os.listdir(save_dir):
                file_path = os.path.join(save_dir, f)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.warning(f"Không thể xóa {file_path}: {e}")
        except Exception as e:
            return jsonify({"status": "error", "message": f"Lỗi với thư mục lưu: {e}"})
    
    filename = secure_filename(file.filename)
    task_id = str(uuid.uuid4())
    video_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{filename}")
    
    file.save(video_path)
    
    video_tasks[task_id] = {
        'status': 'queued',
        'current_frame': 0,
        'total_frames': 0,
        'counts': {},
        'message': '',
        'current_frame_data': None
    }
    
    # Start background thread
    thread = threading.Thread(target=process_video_task, args=(task_id, video_path, save_dir, telegram_enabled, email_enabled))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "success", "task_id": task_id})


@video_bp.route('/api/scan_existing_video', methods=['POST'])
def scan_existing_video():
    data = request.json
    if not data or 'filename' not in data:
        return jsonify({"status": "error", "message": "Thiếu thông tin file."})
        
    filename = secure_filename(data['filename'])
    local_save_enabled = data.get('local_save_enabled', False)
    telegram_enabled = data.get('telegram_enabled', False)
    email_enabled = data.get('email_enabled', False)
    save_dir = data.get('save_dir', '').strip()
    
    if not local_save_enabled:
        save_dir = None
        
    if local_save_enabled and not save_dir:
        return jsonify({"status": "error", "message": "Chưa nhập thư mục lưu ảnh."})
        
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(video_path):
        return jsonify({"status": "error", "message": "File video không tồn tại trên server."})
        
    if save_dir:
        try:
            os.makedirs(save_dir, exist_ok=True)
            # Xóa các file và thư mục cũ trong thư mục nếu có
            for f in os.listdir(save_dir):
                file_path = os.path.join(save_dir, f)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.warning(f"Không thể xóa {file_path}: {e}")
        except Exception as e:
            return jsonify({"status": "error", "message": f"Lỗi với thư mục lưu: {e}"})
        
    task_id = str(uuid.uuid4())
    video_tasks[task_id] = {
        'status': 'queued',
        'current_frame': 0,
        'total_frames': 0,
        'counts': {},
        'message': '',
        'current_frame_data': None
    }
    
    # Start background thread
    thread = threading.Thread(target=process_video_task, args=(task_id, video_path, save_dir, telegram_enabled, email_enabled))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "success", "task_id": task_id})


@video_bp.route('/api/status/<task_id>', methods=['GET'])
def task_status(task_id):
    if task_id not in video_tasks:
        return jsonify({"status": "error", "message": "Task không tồn tại."})
        
    # Loại bỏ dữ liệu ảnh (bytes) trước khi chuyển thành JSON
    task_info = video_tasks[task_id].copy()
    task_info.pop('current_frame_data', None)
    
    return jsonify(task_info)


@video_bp.route('/api/check_dir', methods=['POST'])
def check_dir():
    data = request.json
    if not data or 'save_dir' not in data:
        return jsonify({"status": "error", "message": "Thiếu thư mục."})
    
    save_dir = data['save_dir'].strip()
    if os.path.exists(save_dir) and os.path.isdir(save_dir):
        files = os.listdir(save_dir)
        if len(files) > 0:
            return jsonify({"status": "success", "has_files": True})
            
    return jsonify({"status": "success", "has_files": False})
