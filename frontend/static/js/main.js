// static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    // 0. Xử lý Tab Navigation
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active classes
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Add active class to clicked button and target tab
            btn.classList.add('active');
            const targetId = btn.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');

            // Nếu chuyển sang tab Quản lý Video, tự động tải lại danh sách
            if (targetId === 'manage-tab') {
                fetchVideos();
            }
        });
    });

    // 0.5 Logic Quản lý Video
    const videoListBody = document.getElementById('video-list-body');
    const btnRefreshVideos = document.getElementById('btn-refresh-videos');

    if (btnRefreshVideos) {
        btnRefreshVideos.addEventListener('click', fetchVideos);
    }

    function fetchVideos() {
        videoListBody.innerHTML = `<tr><td colspan="4" style="text-align: center; padding: 2rem; color: var(--text-muted);">Đang tải dữ liệu...</td></tr>`;
        fetch('/api/videos')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    renderVideoList(data.videos);
                } else {
                    videoListBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--danger); padding: 2rem;">Lỗi tải dữ liệu.</td></tr>`;
                }
            })
            .catch(err => {
                console.error("Lỗi fetch videos:", err);
                videoListBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--danger); padding: 2rem;">Không thể kết nối đến máy chủ.</td></tr>`;
            });
    }

    function renderVideoList(videos) {
        if (!videos || videos.length === 0) {
            videoListBody.innerHTML = `<tr><td colspan="4" style="text-align: center; padding: 2rem; color: var(--text-muted);">Không có video nào trên máy chủ.</td></tr>`;
            return;
        }

        videoListBody.innerHTML = "";
        videos.forEach(video => {
            const date = new Date(video.created_at * 1000).toLocaleString('vi-VN');
            const tr = document.createElement('tr');
            tr.className = 'video-row';
            tr.innerHTML = `
                <td style="padding: 1rem; font-family: var(--font-mono); font-size: 0.9em; word-break: break-all;">${video.filename}</td>
                <td style="padding: 1rem;">${video.size} MB</td>
                <td style="padding: 1rem;">${date}</td>
                <td style="padding: 1rem; text-align: center; display: flex; gap: 0.5rem; justify-content: center;">
                    <button class="btn-view" data-filename="${video.filename}">
                        <i class="fas fa-play"></i> Xem
                    </button>
                    <button class="btn-rescan" data-filename="${video.filename}">
                        <i class="fas fa-redo"></i> Quét lại
                    </button>
                    <button class="btn-delete" data-filename="${video.filename}">
                        <i class="fas fa-trash-alt"></i> Xóa
                    </button>
                </td>
            `;
            videoListBody.appendChild(tr);
        });

        // Gắn sự kiện xóa
        document.querySelectorAll('.btn-delete').forEach(btn => {
            btn.addEventListener('click', function() {
                const filename = this.getAttribute('data-filename');
                if (confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn file "${filename}" khỏi máy chủ không?`)) {
                    deleteVideo(filename);
                }
            });
        });

        // Gắn sự kiện Xem
        document.querySelectorAll('.btn-view').forEach(btn => {
            btn.addEventListener('click', function() {
                const filename = this.getAttribute('data-filename');
                openVideoModal(filename);
            });
        });

        // Gắn sự kiện Quét lại
        document.querySelectorAll('.btn-rescan').forEach(btn => {
            btn.addEventListener('click', function() {
                const filename = this.getAttribute('data-filename');
                const localSaveEnabled = videoSaveToggle ? videoSaveToggle.checked : false;
                const emailEnabled = videoEmailToggle ? videoEmailToggle.checked : false;
                
                if (!localSaveEnabled && !emailEnabled) {
                    alert("Vui lòng bật ít nhất một chế độ lưu kết quả (Lưu cục bộ hoặc Gmail) ở Tab Quét Video File!");
                    return;
                }
                
                let saveDirValue = '';
                if (localSaveEnabled) {
                    saveDirValue = prompt(`Nhập thư mục lưu kết quả quét cho video "${filename}"\n(Ví dụ: D:\\KetQua):`);
                    if (!saveDirValue || saveDirValue.trim() === '') {
                        return; // User cancelled or left it empty
                    }
                    saveDirValue = saveDirValue.trim();
                }
                
                if (localSaveEnabled && saveDirValue) {
                    // Check dir first
                    fetch('/api/check_dir', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ save_dir: saveDirValue })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'success' && data.has_files) {
                            const isConfirmed = confirm("CẢNH BÁO: Thư mục này hiện đang có dữ liệu.\nNếu tiếp tục, TOÀN BỘ CÁC FILE CŨ SẼ BỊ XÓA.\nBạn có muốn tiếp tục không?");
                            if (!isConfirmed) return;
                        }
                        startExistingScan(filename, saveDirValue);
                    })
                    .catch(err => {
                        console.error("Lỗi kiểm tra thư mục:", err);
                        startExistingScan(filename, saveDirValue);
                    });
                } else {
                    startExistingScan(filename, '');
                }
            });
        });
    }

    // Modal Logic
    const videoModal = document.getElementById('video-modal');
    const modalVideoPlayer = document.getElementById('modal-video-player');
    const modalVideoTitle = document.getElementById('modal-video-title');
    const btnCloseModal = document.getElementById('btn-close-modal');

    function openVideoModal(filename) {
        modalVideoTitle.innerText = filename;
        modalVideoPlayer.src = `/uploads/${encodeURIComponent(filename)}`;
        videoModal.style.display = 'flex';
        modalVideoPlayer.play();
    }

    btnCloseModal.addEventListener('click', () => {
        videoModal.style.display = 'none';
        modalVideoPlayer.pause();
        modalVideoPlayer.src = '';
    });

    function startExistingScan(filename, saveDirValue) {
        // Switch to offline tab automatically
        document.querySelector('.tab-btn[data-target="offline-tab"]').click();
        
        const localSaveEnabled = videoSaveToggle ? videoSaveToggle.checked : false;
        const emailEnabled = videoEmailToggle ? videoEmailToggle.checked : false;
        
        btnScanVideo.disabled = true;
        btnScanVideo.innerText = "Đang chuẩn bị quét...";
        progressContainer.style.display = "block";
        resultsContainer.style.display = "none";
        progressBar.style.width = "0%";
        statusText.innerText = "Đang kết nối...";
        statsList.innerHTML = "";
        
        fetch('/api/scan_existing_video', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                filename: filename, 
                save_dir: saveDirValue,
                local_save_enabled: localSaveEnabled,
                email_enabled: emailEnabled
            })
        })
        .then(res => res.json())
        .then(data => handleScanResponse(data))
        .catch(err => {
            console.error("Lỗi khi quét lại:", err);
            alert("Đã xảy ra lỗi khi yêu cầu quét lại.");
            resetScanUI();
        });
    }

    function handleScanResponse(data) {
        if(data.status === 'success') {
            currentScanTaskId = data.task_id;
            statusText.innerText = "Đang xử lý...";
            btnScanVideo.innerText = "Đang quét YOLO...";
            btnScanVideo.disabled = true;
            if (btnStopScan) btnStopScan.style.display = 'block';
            
            // Cập nhật src cho màn hình video stream
            const offlineStream = document.getElementById('offline-video-stream');
            offlineStream.src = '/scan_video_feed/' + data.task_id;
            
            // Bắt đầu polling trạng thái
            pollingInterval = setInterval(() => checkTaskStatus(data.task_id), 1000);
        } else {
            alert("Lỗi: " + data.message);
            resetScanUI();
        }
    }

    function deleteVideo(filename) {
        fetch(`/api/videos/${encodeURIComponent(filename)}`, { method: 'DELETE' })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    fetchVideos();
                } else {
                    alert("Lỗi khi xóa: " + data.message);
                }
            })
            .catch(err => {
                console.error("Lỗi xóa video:", err);
                alert("Đã xảy ra lỗi khi xóa video.");
            });
    }

    // 1. Cập nhật đồng hồ thời gian thực
    const clockElement = document.getElementById('live-clock');
    
    function updateClock() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('vi-VN', { hour12: false });
        clockElement.textContent = timeString;
    }
    
    setInterval(updateClock, 1000);
    updateClock(); // Chạy ngay lần đầu

    // 2. Xử lý đổi IP Camera
    const btnUpdateCam = document.getElementById('btn-update-cam');
    const btnStopCam = document.getElementById('btn-stop-cam');
    const btnToggleScan = document.getElementById('btn-toggle-scan');
    let isLiveScanning = false;
    const inputCamIp = document.getElementById('camera-ip');
    const videoStream = document.getElementById('video-stream');
    const liveSaveToggle = document.getElementById('live-save-toggle');
    const liveSaveOptions = document.getElementById('live-save-options');
    const liveSaveDir = document.getElementById('live-save-dir');
    const streamLoading = document.getElementById('stream-loading');
    
    if (liveSaveToggle) {
        liveSaveToggle.addEventListener('change', (e) => {
            liveSaveOptions.style.display = e.target.checked ? 'block' : 'none';
        });
    }

    // Xử lý chuyển đổi chế độ Webcam / IP Camera
    const btnModeWebcam = document.getElementById('btn-mode-webcam');
    const btnModeIpcam = document.getElementById('btn-mode-ipcam');
    const labelCameraSource = document.getElementById('label-camera-source');

    if (btnModeWebcam && btnModeIpcam && inputCamIp) {
        btnModeWebcam.addEventListener('click', () => {
            btnModeWebcam.classList.add('active');
            btnModeIpcam.classList.remove('active');
            labelCameraSource.innerText = "Nguồn Camera (Index)";
            inputCamIp.value = "0";
            inputCamIp.placeholder = "Ví dụ: 0, 1 hoặc 2";
        });

        btnModeIpcam.addEventListener('click', () => {
            btnModeIpcam.classList.add('active');
            btnModeWebcam.classList.remove('active');
            labelCameraSource.innerText = "Nguồn Camera (IP/URL)";
            inputCamIp.value = "http://192.168.1.100:8080/video";
            inputCamIp.placeholder = "Ví dụ: http://192.168.1.100:8080/video";
        });
    }
    
    btnUpdateCam.addEventListener('click', () => {
        const newUrl = inputCamIp.value;
        let saveDirValue = null;
        
        if (liveSaveToggle && liveSaveToggle.checked) {
            saveDirValue = liveSaveDir.value.trim();
            if (!saveDirValue) {
                alert("Vui lòng nhập thư mục lưu ảnh (Local)!");
                return;
            }
            
            // Disable button and show checking text
            const originalText = btnUpdateCam.innerText;
            btnUpdateCam.innerText = "Đang kiểm tra...";
            btnUpdateCam.disabled = true;
            
            fetch('/api/check_dir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ save_dir: saveDirValue })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.has_files) {
                    const isConfirmed = confirm("CẢNH BÁO: Thư mục này hiện đang có dữ liệu.\n\nNếu bạn tiếp tục, TOÀN BỘ CÁC FILE CŨ TRONG THƯ MỤC NÀY SẼ BỊ XÓA để lưu kết quả quét mới.\n\nBạn có chắc chắn muốn tiếp tục không?");
                    if (!isConfirmed) {
                        btnUpdateCam.disabled = false;
                        btnUpdateCam.innerText = "Mở / Cập nhật Camera";
                        return; // Hủy quá trình
                    }
                }
                startLiveCameraUpdate(newUrl, saveDirValue, originalText);
            })
            .catch(err => {
                console.error("Lỗi kiểm tra thư mục:", err);
                startLiveCameraUpdate(newUrl, saveDirValue, originalText); // Vẫn thử kết nối
            });
        } else {
            startLiveCameraUpdate(newUrl, saveDirValue, btnUpdateCam.innerText);
        }
    });
    
    function startLiveCameraUpdate(newUrl, saveDirValue, originalText) {
        // Hiển thị loading và ẩn ảnh tĩnh
        videoStream.style.display = 'none';
        const placeholder = document.getElementById('video-placeholder');
        if (placeholder) placeholder.style.display = 'none';
        if (streamLoading) streamLoading.style.display = 'flex';
        
        // Đếm ngược 5 giây trong khi chờ backend kiểm tra camera
        btnUpdateCam.disabled = true;
        let countdown = 5;
        btnUpdateCam.innerText = `Đang kết nối... (${countdown}s)`;
        const countdownTimer = setInterval(() => {
            countdown--;
            if (countdown > 0) {
                btnUpdateCam.innerText = `Đang kết nối... (${countdown}s)`;
            } else {
                clearInterval(countdownTimer);
            }
        }, 1000);

        // Gửi request lên server (backend sẽ chờ tối đa 5s để xác nhận)
        fetch('/update_camera', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: newUrl, save_dir: saveDirValue })
        })
        .then(response => response.json())
        .then(data => {
            clearInterval(countdownTimer);
            if(data.status === 'success') {
                videoStream.src = "/video_feed?" + new Date().getTime();
                videoStream.style.display = 'block';
                if (streamLoading) streamLoading.style.display = 'none';
                
                btnUpdateCam.innerText = "Đã kết nối ✓";
                btnUpdateCam.style.background = "var(--success)";
                btnUpdateCam.style.color = "#fff";
                // Giữ disabled để không bấm lại
                
                if (btnStopCam) btnStopCam.style.display = 'block';
                if (btnToggleScan) {
                    btnToggleScan.style.display = 'block';
                    isLiveScanning = false;
                    btnToggleScan.innerHTML = '<i class="fas fa-play"></i> Bắt đầu quét';
                    btnToggleScan.style.backgroundColor = 'var(--secondary, #8b5cf6)';
                }
            } else {
                // Kết nối thất bại — báo lỗi rõ ràng
                if (streamLoading) streamLoading.style.display = 'none';
                const placeholder = document.getElementById('video-placeholder');
                if (placeholder) placeholder.style.display = 'flex';
                
                btnUpdateCam.innerText = "❌ Kết nối thất bại";
                btnUpdateCam.style.background = "var(--danger, #e74c3c)";
                btnUpdateCam.style.color = "#fff";
                btnUpdateCam.disabled = true;
                
                alert("❌ Lỗi kết nối camera!\n\n" + data.message);
                
                // Sau 3 giây, reset nút để cho phép thử lại
                setTimeout(() => {
                    btnUpdateCam.innerText = "Mở / Cập nhật Camera";
                    btnUpdateCam.style.background = "";
                    btnUpdateCam.style.color = "";
                    btnUpdateCam.disabled = false;
                }, 3000);
            }
        })
        .catch(err => {
            clearInterval(countdownTimer);
            console.error("Lỗi:", err);
            if (streamLoading) streamLoading.style.display = 'none';
            const placeholder = document.getElementById('video-placeholder');
            if (placeholder) placeholder.style.display = 'flex';
            
            btnUpdateCam.innerText = "❌ Lỗi kết nối server";
            btnUpdateCam.style.background = "var(--danger, #e74c3c)";
            setTimeout(() => {
                btnUpdateCam.innerText = "Mở / Cập nhật Camera";
                btnUpdateCam.style.background = "";
                btnUpdateCam.disabled = false;
            }, 3000);
        });
    }
    
    if (btnStopCam) {
        btnStopCam.addEventListener('click', () => {
            btnStopCam.innerText = "Đang dừng...";
            btnStopCam.disabled = true;
            fetch('/api/stop_camera', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    videoStream.style.display = 'none';
                    videoStream.src = '';
                    const placeholder = document.getElementById('video-placeholder');
                    if (placeholder) placeholder.style.display = 'flex';
                    
                    btnStopCam.style.display = 'none';
                    if (btnToggleScan) btnToggleScan.style.display = 'none';
                    btnStopCam.innerText = "Dừng Camera";
                    btnStopCam.disabled = false;
                    
                    // Phục hồi lại nút Mở / Cập nhật Camera
                    btnUpdateCam.innerText = "Mở / Cập nhật Camera";
                    btnUpdateCam.style.background = "";
                    btnUpdateCam.disabled = false;
                    
                    const liveStatsList = document.getElementById('live-stats-list');
                    if(liveStatsList) {
                        liveStatsList.innerHTML = "<li><span class='stat-label' style='color: #888; font-style: italic;'>Đã dừng phát hiện.</span></li>";
                    }
                }
            })
            .catch(err => {
                console.error("Lỗi khi dừng camera:", err);
                btnStopCam.innerText = "Dừng Camera";
                btnStopCam.disabled = false;
            });
        });
    }

    if (btnToggleScan) {
        btnToggleScan.addEventListener('click', () => {
            const newState = !isLiveScanning;
            btnToggleScan.disabled = true;
            
            fetch('/api/toggle_live_scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active: newState })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    isLiveScanning = data.live_yolo_active;
                    if (isLiveScanning) {
                        btnToggleScan.innerHTML = '<i class="fas fa-pause"></i> Dừng quét';
                        btnToggleScan.style.backgroundColor = '#f39c12'; // Orange
                    } else {
                        btnToggleScan.innerHTML = '<i class="fas fa-play"></i> Bắt đầu quét';
                        btnToggleScan.style.backgroundColor = 'var(--secondary, #8b5cf6)';
                    }
                }
                btnToggleScan.disabled = false;
            })
            .catch(err => {
                console.error("Lỗi chuyển đổi quét:", err);
                btnToggleScan.disabled = false;
            });
        });
    }

    // Nút ẩn/hiện Bảng điều khiển để mở rộng Video (Live Tab)
    const btnToggleLiveStats = document.getElementById('btn-toggle-live-stats');
    const liveTab = document.getElementById('live-tab');
    const liveLeftSidebar = liveTab ? liveTab.querySelector('.sidebar:not(.right-sidebar)') : null;
    
    if (btnToggleLiveStats && liveLeftSidebar && liveTab) {
        btnToggleLiveStats.addEventListener('click', () => {
            if (liveLeftSidebar.style.display === 'none') {
                liveLeftSidebar.style.display = 'flex';
                liveTab.style.gridTemplateColumns = '320px 1fr 320px';
                btnToggleLiveStats.innerHTML = '<i class="fas fa-expand-arrows-alt"></i> Mở rộng Video';
            } else {
                liveLeftSidebar.style.display = 'none';
                liveTab.style.gridTemplateColumns = '1fr 320px';
                btnToggleLiveStats.innerHTML = '<i class="fas fa-compress-arrows-alt"></i> Thu nhỏ Video';
            }
        });
    }

    // Polling cho Live Camera Stats
    const liveStatsList = document.getElementById('live-stats-list');
    setInterval(() => {
        // Chỉ fetch khi tab Live đang active
        if (liveTab && liveTab.classList.contains('active')) {
            fetch('/api/live_status')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'running' && data.counts) {
                    displayLiveResults(data.counts);
                }
            })
            .catch(err => console.error("Lỗi lấy live status:", err));
        }
    }, 1000);

    function displayLiveResults(counts) {
        if (!counts || Object.keys(counts).length === 0) {
            liveStatsList.innerHTML = "<li><span class='stat-label' style='color: #888; font-style: italic;'>Đang chờ phát hiện...</span></li>";
            return;
        }

        const waitMsg = liveStatsList.querySelector('li span.stat-label[style*="italic"]');
        if (waitMsg) {
            liveStatsList.innerHTML = "";
        }

        for (const [clsName, count] of Object.entries(counts)) {
            const safeId = "live-stat-" + clsName.replace(/\W/g, '');
            let existingLi = document.getElementById(safeId);
            
            if (existingLi) {
                const valSpan = existingLi.querySelector('.stat-value');
                if (valSpan) {
                    valSpan.innerText = count + " lần";
                }
            } else {
                const li = document.createElement('li');
                li.id = safeId;
                li.innerHTML = `
                    <span class='stat-label' style='text-transform: capitalize;'>${clsName}</span>
                    <span class='stat-value highlight'>${count} lần</span>
                `;
                liveStatsList.appendChild(li);
            }
        }
    }

    // 3. Xử lý quét Video Offline
    const btnScanVideo = document.getElementById('btn-scan-video');
    const btnStopScan = document.getElementById('btn-stop-scan');
    const videoUpload = document.getElementById('video-upload');
    const saveDir = document.getElementById('save-dir');
    const progressContainer = document.getElementById('scan-progress-container');
    const progressBar = document.getElementById('scan-progress-bar');
    const statusText = document.getElementById('scan-status-text');
    const resultsContainer = document.getElementById('scan-results-container');
    const statsList = document.getElementById('scan-stats-list');
    const videoSaveToggle = document.getElementById('video-save-toggle');
    const videoSaveOptions = document.getElementById('video-save-options');
    const videoEmailToggle = document.getElementById('video-email-toggle');
    
    let pollingInterval = null;
    let currentScanTaskId = null;

    if (videoSaveToggle && videoSaveOptions) {
        videoSaveToggle.addEventListener('change', (e) => {
            videoSaveOptions.style.display = e.target.checked ? 'block' : 'none';
        });
    }

    btnScanVideo.addEventListener('click', () => {
        if (!videoUpload.files || videoUpload.files.length === 0) {
            alert("Vui lòng chọn file video!");
            return;
        }
        
        const localSaveEnabled = videoSaveToggle ? videoSaveToggle.checked : false;
        const emailEnabled = videoEmailToggle ? videoEmailToggle.checked : false;
        const saveDirValue = saveDir.value.trim();
        
        if (localSaveEnabled && !saveDirValue) {
            alert("Vui lòng nhập thư mục lưu ảnh!");
            return;
        }

        if (!localSaveEnabled && !emailEnabled) {
            alert("Vui lòng chọn ít nhất một chế độ lưu kết quả (Lưu cục bộ hoặc Gmail)!");
            return;
        }
        
        const file = videoUpload.files[0];
        const formData = new FormData();
        formData.append('video', file);
        formData.append('local_save_enabled', localSaveEnabled);

        formData.append('email_enabled', emailEnabled);
        formData.append('save_dir', localSaveEnabled ? saveDirValue : '');
        
        // Disable nút để tránh click liên tục
        btnScanVideo.disabled = true;
        
        if (localSaveEnabled) {
            btnScanVideo.innerText = "Đang kiểm tra thư mục...";
            // Bước 1: Kiểm tra xem thư mục có dữ liệu không
            fetch('/api/check_dir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ save_dir: saveDirValue })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.has_files) {
                    const isConfirmed = confirm("CẢNH BÁO: Thư mục này hiện đang có dữ liệu.\n\nNếu bạn tiếp tục, TOÀN BỘ CÁC FILE CŨ TRONG THƯ MỤC NÀY SẼ BỊ XÓA để lưu kết quả quét mới.\n\nBạn có chắc chắn muốn tiếp tục không?");
                    if (!isConfirmed) {
                        btnScanVideo.disabled = false;
                        btnScanVideo.innerText = "Bắt đầu quét";
                        return; // Hủy quá trình
                    }
                }
                // Bước 2: Bắt đầu tải video và quét
                startUpload(formData);
            })
            .catch(err => {
                console.error("Lỗi kiểm tra thư mục:", err);
                startUpload(formData); // Nếu lỗi kiểm tra thì vẫn thử upload
            });
        } else {
            startUpload(formData);
        }
    });
    
    function startUpload(formData) {
        // Reset UI
        btnScanVideo.disabled = true;
        btnScanVideo.innerText = "Đang tải lên...";
        progressContainer.style.display = "block";
        resultsContainer.style.display = "none";
        progressBar.style.width = "0%";
        statusText.innerText = "Đang tải video lên server...";
        statsList.innerHTML = "";
        
        fetch('/api/upload_video', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => handleScanResponse(data))
        .catch(err => {
            console.error("Lỗi tải video:", err);
            alert("Đã xảy ra lỗi khi tải video.");
            resetScanUI();
        });
    }
    
    // Nút ẩn/hiện Bảng điều khiển để mở rộng Video
    const btnToggleStats = document.getElementById('btn-toggle-stats');
    const offlineTab = document.getElementById('offline-tab');
    const leftSidebar = offlineTab ? offlineTab.querySelector('.sidebar:not(.right-sidebar)') : null;
    
    if (btnToggleStats && leftSidebar && offlineTab) {
        btnToggleStats.addEventListener('click', () => {
            if (leftSidebar.style.display === 'none') {
                // Đang ẩn -> Hiện lại
                leftSidebar.style.display = 'flex';
                offlineTab.style.gridTemplateColumns = '320px 1fr 320px';
                btnToggleStats.innerHTML = '<i class="fas fa-expand-arrows-alt"></i> Mở rộng Video';
            } else {
                // Đang hiện -> Ẩn đi
                leftSidebar.style.display = 'none';
                offlineTab.style.gridTemplateColumns = '1fr 320px';
                btnToggleStats.innerHTML = '<i class="fas fa-compress-arrows-alt"></i> Thu nhỏ Video';
            }
        });
    }
    
    function checkTaskStatus(taskId) {
        fetch('/api/status/' + taskId)
        .then(res => res.json())
        .then(data => {
            if(data.status === 'error') {
                clearInterval(pollingInterval);
                alert("Lỗi xử lý video: " + data.message);
                resetScanUI();
            } else if(data.status === 'processing') {
                // total_frames có thể là 0 nếu chưa fetch kịp metadata
                const total = data.total_frames || 1;
                const current = data.current_frame || 0;
                let percent = Math.floor((current / total) * 100);
                if (percent > 100) percent = 100;
                
                progressBar.style.width = percent + "%";
                statusText.innerText = `Đang quét: ${percent}% (${current}/${data.total_frames} frames)`;
                
                // Cập nhật thống kê trực tiếp
                if (data.counts) {
                    displayResults(data.counts, "");
                }
            } else if(data.status === 'completed' || data.status === 'stopped') {
                clearInterval(pollingInterval);
                progressBar.style.width = "100%";
                statusText.innerText = "Hoàn thành!";
                
                // Hiển thị kết quả
                displayResults(data.counts, data.message);
                resetScanUI(true);
            }
        })
        .catch(err => console.error("Lỗi khi lấy trạng thái:", err));
    }
    
    function displayResults(counts, message) {
        resultsContainer.style.display = "block";
        
        if (!counts || Object.keys(counts).length === 0) {
            statsList.innerHTML = "<li><span class='stat-label' style='color: #888; font-style: italic;'>Đang chờ phát hiện...</span></li>";
            return;
        }

        // Xóa thông báo chờ phát hiện nếu có
        const waitMsg = statsList.querySelector('li span.stat-label[style*="italic"]');
        if (waitMsg) {
            statsList.innerHTML = "";
        }

        for (const [clsName, count] of Object.entries(counts)) {
            // Tìm xem thẻ li cho class này đã có chưa
            const safeId = "stat-" + clsName.replace(/\W/g, '');
            let existingLi = document.getElementById(safeId);
            
            if (existingLi) {
                // Cập nhật số
                const valSpan = existingLi.querySelector('.stat-value');
                if (valSpan) {
                    valSpan.innerText = count + " lần";
                }
            } else {
                // Tạo mới
                const li = document.createElement('li');
                li.id = safeId;
                li.innerHTML = `
                    <span class='stat-label' style='text-transform: capitalize;'>${clsName}</span>
                    <span class='stat-value highlight'>${count} lần</span>
                `;
                statsList.appendChild(li);
            }
        }
        
        if (message) {
            const msgLi = document.createElement('li');
            msgLi.style.marginTop = "10px";
            msgLi.style.color = "var(--success)";
            msgLi.style.fontSize = "0.9em";
            msgLi.innerText = message;
            statsList.appendChild(msgLi);
        }
    }
    
    function resetScanUI(success = false) {
        btnScanVideo.disabled = false;
        btnScanVideo.innerText = "Bắt đầu quét";
        if (btnStopScan) btnStopScan.style.display = 'none';
        if(!success) {
            progressContainer.style.display = "none";
        }
        currentScanTaskId = null;
    }
    
    if (btnStopScan) {
        btnStopScan.addEventListener('click', () => {
            if (!currentScanTaskId) return;
            btnStopScan.innerText = "Đang dừng...";
            btnStopScan.disabled = true;
            fetch('/api/stop_scan/' + currentScanTaskId, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    btnStopScan.innerText = "Đã yêu cầu dừng...";
                }
            })
            .catch(err => {
                console.error("Lỗi khi dừng quét:", err);
                btnStopScan.innerText = "Dừng quét";
                btnStopScan.disabled = false;
            });
        });
    }
    
    // 4. Xử lý quét Ảnh tĩnh
    const btnScanImage = document.getElementById('btn-scan-image');
    const imageUpload = document.getElementById('image-upload');
    const imageSaveDir = document.getElementById('image-save-dir');
    const imageStatus = document.getElementById('image-scan-status');
    const imagePlaceholder = document.getElementById('image-placeholder');
    const imageResultStream = document.getElementById('image-result-stream');
    const imageResultsContainer = document.getElementById('image-results-container');
    const imageStatsList = document.getElementById('image-stats-list');

    if (btnScanImage) {
        btnScanImage.addEventListener('click', () => {
            if (!imageUpload.files || imageUpload.files.length === 0) {
                alert("Vui lòng chọn file hình ảnh!");
                return;
            }
            
            const file = imageUpload.files[0];
            const formData = new FormData();
            formData.append('image', file);
            
            const saveDirValue = imageSaveDir.value.trim();
            if (saveDirValue) {
                formData.append('save_dir', saveDirValue);
            }
            
            // UI Update
            btnScanImage.disabled = true;
            btnScanImage.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang xử lý...';
            imageStatus.style.display = 'block';
            imageStatus.innerText = 'Đang tải ảnh lên và quét YOLO...';
            imageStatus.style.color = 'var(--text-main)';
            
            // Preview locally immediately
            const reader = new FileReader();
            reader.onload = function(e) {
                imagePlaceholder.style.display = 'none';
                imageResultStream.style.display = 'block';
                imageResultStream.src = e.target.result;
            }
            reader.readAsDataURL(file);

            fetch('/api/scan_image', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                btnScanImage.disabled = false;
                btnScanImage.innerHTML = '<i class="fas fa-search"></i> Quét Hình Ảnh';
                
                if (data.status === 'success') {
                    imageStatus.innerText = data.message || 'Quét thành công!';
                    imageStatus.style.color = 'var(--success)';
                    
                    // Display Base64 result image
                    if (data.image) {
                        imageResultStream.src = "data:image/jpeg;base64," + data.image;
                    }
                    
                    // Display stats
                    imageResultsContainer.style.display = 'block';
                    imageStatsList.innerHTML = '';
                    
                    if (!data.counts || Object.keys(data.counts).length === 0) {
                        imageStatsList.innerHTML = "<li><span class='stat-label' style='color: #888; font-style: italic;'>Không phát hiện vật thể nào.</span></li>";
                    } else {
                        for (const [clsName, count] of Object.entries(data.counts)) {
                            const li = document.createElement('li');
                            li.innerHTML = `
                                <span class='stat-label' style='text-transform: capitalize;'>${clsName}</span>
                                <span class='stat-value highlight'>${count}</span>
                            `;
                            imageStatsList.appendChild(li);
                        }
                    }
                } else {
                    imageStatus.innerText = 'Lỗi: ' + data.message;
                    imageStatus.style.color = 'var(--danger)';
                    alert("Lỗi: " + data.message);
                }
            })
            .catch(err => {
                console.error("Lỗi quét ảnh:", err);
                btnScanImage.disabled = false;
                btnScanImage.innerHTML = '<i class="fas fa-search"></i> Quét Hình Ảnh';
                imageStatus.innerText = 'Lỗi kết nối máy chủ.';
                imageStatus.style.color = 'var(--danger)';
            });
        });
    }



    // ============================================================
    // 7. Gmail Config
    // ============================================================
    const emailEnabled = document.getElementById('email-enabled');
    const emailSender = document.getElementById('email-sender');
    const emailPassword = document.getElementById('email-password');
    const emailReceiver = document.getElementById('email-receiver');
    const emailCooldown = document.getElementById('email-cooldown');
    const btnEmailSave = document.getElementById('btn-email-save');
    const btnEmailTest = document.getElementById('btn-email-test');
    const emailStatusMsg = document.getElementById('email-status-msg');
    const liveEmailToggle = document.getElementById('live-email-toggle');

    function showEmailStatus(msg, color = 'var(--text-muted)') {
        if (emailStatusMsg) {
            emailStatusMsg.innerText = msg;
            emailStatusMsg.style.color = color;
            setTimeout(() => {
                if (emailStatusMsg.innerText === msg) {
                    emailStatusMsg.innerText = '';
                }
            }, 5000);
        }
    }

    function loadEmailConfig() {
        fetch('/api/email/config')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.config) {
                    const cfg = data.config;
                    if (emailEnabled) emailEnabled.checked = cfg.enabled || false;
                    if (liveEmailToggle) liveEmailToggle.checked = cfg.enabled || false;
                    if (emailSender) emailSender.value = cfg.sender_email || '';
                    if (emailReceiver) emailReceiver.value = cfg.receiver_email || '';
                    if (emailCooldown) emailCooldown.value = cfg.cooldown || 60;
                }
            })
            .catch(err => console.error('Lỗi load Gmail config:', err));
    }

    loadEmailConfig();

    // Đồng bộ thay đổi từ checkbox Live Email
    if (liveEmailToggle) {
        liveEmailToggle.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            if (emailEnabled) emailEnabled.checked = isChecked;
            
            fetch('/api/email/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: isChecked })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status !== 'success') {
                    showEmailStatus('❌ Không thể lưu trạng thái Gmail', 'var(--danger)');
                }
            })
            .catch(err => console.error('Lỗi cập nhật trạng thái Gmail:', err));
        });
    }

    // Đồng bộ thay đổi từ checkbox Gmail Config Panel
    if (emailEnabled) {
        emailEnabled.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            if (liveEmailToggle) liveEmailToggle.checked = isChecked;
            
            fetch('/api/email/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: isChecked })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status !== 'success') {
                    showEmailStatus('❌ Không thể lưu trạng thái Gmail', 'var(--danger)');
                }
            })
            .catch(err => console.error('Lỗi cập nhật trạng thái Gmail:', err));
        });
    }

    // Lưu cấu hình Gmail
    if (btnEmailSave) {
        btnEmailSave.addEventListener('click', () => {
            const payload = {
                enabled: emailEnabled ? emailEnabled.checked : false,
                sender_email: emailSender ? emailSender.value.trim() : '',
                receiver_email: emailReceiver ? emailReceiver.value.trim() : '',
                cooldown: emailCooldown ? parseInt(emailCooldown.value) || 60 : 60,
            };

            if (emailPassword && emailPassword.value.trim()) {
                payload.app_password = emailPassword.value.trim();
            }

            btnEmailSave.disabled = true;
            btnEmailSave.innerHTML = '⏳ Đang lưu...';

            fetch('/api/email/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                btnEmailSave.disabled = false;
                btnEmailSave.innerHTML = '💾 Lưu cấu hình';

                if (data.status === 'success') {
                    showEmailStatus('✅ Đã lưu cấu hình Gmail!', 'var(--success)');
                    if (emailPassword) emailPassword.value = '';
                } else {
                    showEmailStatus('❌ ' + data.message, 'var(--danger)');
                }
            })
            .catch(err => {
                btnEmailSave.disabled = false;
                btnEmailSave.innerHTML = '💾 Lưu cấu hình';
                showEmailStatus('❌ Lỗi kết nối server', 'var(--danger)');
            });
        });
    }

    // Test kết nối Gmail
    if (btnEmailTest) {
        btnEmailTest.addEventListener('click', () => {
            btnEmailTest.disabled = true;
            btnEmailTest.innerHTML = '⏳ Đang gửi mail...';

            fetch('/api/email/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            })
            .then(res => res.json())
            .then(data => {
                btnEmailTest.disabled = false;
                btnEmailTest.innerHTML = '📧 Test';

                if (data.status === 'success') {
                    showEmailStatus('✅ ' + data.message, 'var(--success)');
                } else {
                    showEmailStatus('❌ ' + data.message, 'var(--danger)');
                }
            })
            .catch(err => {
                btnEmailTest.disabled = false;
                btnEmailTest.innerHTML = '📧 Test';
                showEmailStatus('❌ Lỗi kết nối server', 'var(--danger)');
            });
        });
    }
});
