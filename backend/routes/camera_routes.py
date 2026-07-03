# backend/routes/camera_routes.py
# Routes: /video_feed, /api/live_status, /update_camera,
#          /api/stop_camera, /api/toggle_live_scan

import os
import time
import shutil

from flask import Blueprint, Response, request, jsonify

import camera as cam
from camera import CameraStream, generate_frames
from config import model, logger

camera_bp = Blueprint('camera', __name__)


@camera_bp.route('/video_feed')
def video_feed():
    # Route này trả về luồng video liên tục
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@camera_bp.route('/api/live_status')
def live_status():
    if cam.camera_stream is None:
        return jsonify({'status': 'stopped', 'counts': {}})
    with cam.camera_stream.read_lock:
        counts_copy = cam.camera_stream.counts.copy()
    return jsonify({'status': 'running', 'counts': counts_copy})


@camera_bp.route('/update_camera', methods=['POST'])
def update_camera():
    data = request.json
    if 'url' in data:
        new_url = data['url']
        if new_url.strip() == "0":
            cam.current_camera_url = 0
        else:
            cam.current_camera_url = new_url
            
        cam.current_camera_save_dir = data.get('save_dir')
        if cam.current_camera_save_dir and cam.current_camera_save_dir.strip() == '':
            cam.current_camera_save_dir = None
            
        if cam.current_camera_save_dir:
            try:
                os.makedirs(cam.current_camera_save_dir, exist_ok=True)
                for f in os.listdir(cam.current_camera_save_dir):
                    file_path = os.path.join(cam.current_camera_save_dir, f)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception:
                        pass
            except Exception as e:
                return jsonify({"status": "error", "message": f"Lỗi với thư mục lưu: {e}"})
            
        # Khởi động lại camera stream ngay lập tức
        cam.camera_active = True
        cam.live_yolo_active = False
        cam.release_camera_stream()
        with cam.stream_lock:
            cam.camera_stream = CameraStream(
                src=cam.current_camera_url,
                model=model,
                save_dir=cam.current_camera_save_dir
            )
            cam.camera_stream.start()
        logger.info(f"Camera stream started for source: {cam.current_camera_url}")
        
        # Chờ tối đa 5 giây để background thread thực sự mở camera
        timeout = 5.0
        interval = 0.2
        elapsed = 0.0
        while elapsed < timeout:
            time.sleep(interval)
            elapsed += interval
            if cam.camera_stream.connected or cam.camera_stream.connect_error:
                break
        
        if cam.camera_stream.connect_error or not cam.camera_stream.connected:
            # Camera không mở được — dừng stream và báo lỗi
            cam.release_camera_stream()
            err_msg = f"Không thể kết nối đến camera: {cam.current_camera_url}. Vui lòng kiểm tra IP, cổng hoặc kết nối mạng."
            logger.error(err_msg)
            return jsonify({"status": "error", "message": err_msg})
        
        return jsonify({"status": "success", "message": "Đã kết nối camera thành công!"})
    return jsonify({"status": "error", "message": "Thiếu thông tin URL."})


@camera_bp.route('/api/stop_camera', methods=['POST'])
def stop_camera():
    cam.camera_active = False
    cam.live_yolo_active = False
    cam.release_camera_stream()
    return jsonify({"status": "success", "message": "Đã dừng camera."})


@camera_bp.route('/api/toggle_live_scan', methods=['POST'])
def toggle_live_scan():
    data = request.json
    if data and 'active' in data:
        cam.live_yolo_active = bool(data['active'])
        
        # Reset counts khi bắt đầu scan mới
        if cam.live_yolo_active and cam.camera_stream:
            with cam.camera_stream.read_lock:
                cam.camera_stream.counts = {}
                
        return jsonify({"status": "success", "live_yolo_active": cam.live_yolo_active})
    return jsonify({"status": "error", "message": "Invalid request"})
