# backend/routes/image_routes.py
# Routes: /api/scan_image

import os
import uuid

import cv2
import numpy as np
import base64
from flask import Blueprint, request, jsonify

from config import model, model_lock, CONF_THRESHOLD, logger

image_bp = Blueprint('image', __name__)


@image_bp.route('/api/scan_image', methods=['POST'])
def scan_image():
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "Không tìm thấy file hình ảnh."})
        
    file = request.files['image']
    save_dir = request.form.get('save_dir', '').strip()
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "Tên file rỗng."})
        
    try:
        # Đọc file ảnh trực tiếp vào bộ nhớ bằng OpenCV
        nparr = np.frombuffer(file.read(), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({"status": "error", "message": "File không phải là hình ảnh hợp lệ."})
            
        annotated_frame = frame.copy()
        counts = {}
        
        # Dự đoán bằng YOLO
        if model:
            with model_lock:
                results = model.predict(source=frame, conf=CONF_THRESHOLD, show=False, verbose=False)
            annotated_frame = results[0].plot()
            
            if len(results) > 0 and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                names = model.names
                
                # Đếm vật thể
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    cls_name = names[cls_id]
                    counts[cls_name] = counts.get(cls_name, 0) + 1
                    
                # Lưu ảnh nếu có thư mục lưu
                if save_dir:
                    try:
                        os.makedirs(save_dir, exist_ok=True)
                        for cls_name in counts.keys():
                            cls_dir = os.path.join(save_dir, cls_name)
                            os.makedirs(cls_dir, exist_ok=True)
                            
                            # Tên file cho ảnh tĩnh (cùng 1 file sẽ ghi đè hoặc tạo mới bằng uuid)
                            file_id = str(uuid.uuid4())[:8]
                            frame_name = f"image_{file_id}_{cls_name}.jpg"
                            save_path = os.path.join(cls_dir, frame_name)
                            cv2.imwrite(save_path, annotated_frame)
                    except Exception as e:
                        logger.warning(f"Không thể lưu ảnh tĩnh: {e}")
        
        # Chuyển đổi ảnh kết quả sang định dạng Base64
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        if not ret:
            return jsonify({"status": "error", "message": "Không thể xử lý ảnh kết quả."})
            
        b64_img = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            "status": "success",
            "image": b64_img,
            "counts": counts,
            "message": f"Đã phát hiện {sum(counts.values())} vật thể."
        })
        
    except Exception as e:
        logger.error(f"Lỗi khi xử lý hình ảnh: {e}")
        return jsonify({"status": "error", "message": str(e)})
