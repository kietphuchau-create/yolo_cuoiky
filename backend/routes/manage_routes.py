# backend/routes/manage_routes.py
# Routes: /api/videos, /api/videos/<filename>, /uploads/<filename>

import os

from flask import Blueprint, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from config import UPLOAD_FOLDER

manage_bp = Blueprint('manage', __name__)


@manage_bp.route('/api/videos', methods=['GET'])
def list_videos():
    videos = []
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path) and filename.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                stat = os.stat(file_path)
                size_mb = stat.st_size / (1024 * 1024)
                videos.append({
                    "filename": filename,
                    "size": round(size_mb, 2),
                    "created_at": stat.st_mtime
                })
        # Sắp xếp mới nhất lên đầu
        videos.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({"status": "success", "videos": videos})


@manage_bp.route('/api/videos/<filename>', methods=['DELETE'])
def delete_video(filename):
    safe_filename = secure_filename(filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_filename)
    
    if os.path.exists(file_path) and os.path.isfile(file_path):
        try:
            os.remove(file_path)
            return jsonify({"status": "success", "message": "Đã xóa video."})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Không thể xóa: {e}"})
    return jsonify({"status": "error", "message": "File không tồn tại."})


@manage_bp.route('/uploads/<filename>')
def serve_video(filename):
    safe_filename = secure_filename(filename)
    return send_from_directory(UPLOAD_FOLDER, safe_filename)
