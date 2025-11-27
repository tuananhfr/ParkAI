import React, { useEffect, useState, useRef } from "react";

// ==================== Camera Component with Barrier Control ====================
const CameraView = ({ backendUrl, wsUrl, onHistoryUpdate }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [detections, setDetections] = useState([]);
  const [plateText, setPlateText] = useState("");
  const [plateSource, setPlateSource] = useState(""); // "auto" | "manual"
  const [plateConfidence, setPlateConfidence] = useState(0);
  const [cannotReadPlate, setCannotReadPlate] = useState(false);
  const [isOpening, setIsOpening] = useState(false);
  const [cameraInfo, setCameraInfo] = useState(null);
  const [userEdited, setUserEdited] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const pcRef = useRef(null);
  const wsRef = useRef(null);
  const animationFrameRef = useRef(null);
  const lastDetectionsRef = useRef([]);
  const lastDetectionTimeRef = useRef(0);

  useEffect(() => {
    fetchCameraInfo();
    startWebRTC();
    connectWebSocket();
    startDrawLoop();

    // Update thời gian mỗi giây
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => {
      cleanup();
      clearInterval(timeInterval);
    };
  }, []);

  const fetchCameraInfo = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/camera/info`);
      const data = await response.json();
      if (data.success) {
        setCameraInfo(data.camera);
      }
    } catch (err) {
      console.error("Failed to fetch camera info:", err);
    }
  };

  const startWebRTC = async () => {
    try {
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
      });

      pcRef.current = pc;

      pc.ontrack = (event) => {
        if (videoRef.current && event.streams[0]) {
          videoRef.current.srcObject = event.streams[0];
          setIsConnected(true);

          videoRef.current.onloadeddata = () => {
            setIsVideoLoaded(true);
          };
        }
      };

      pc.onconnectionstatechange = () => {
        if (
          pc.connectionState === "failed" ||
          pc.connectionState === "closed"
        ) {
          setError("WebRTC connection lost");
          setIsConnected(false);
          setTimeout(() => {
            setError(null);
            startWebRTC();
          }, 3000);
        }
      };

      const offer = await pc.createOffer({
        offerToReceiveVideo: true,
        offerToReceiveAudio: false,
      });

      await pc.setLocalDescription(offer);

      const response = await fetch(`${backendUrl}/offer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sdp: offer.sdp, type: offer.type }),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const answer = await response.json();
      await pc.setRemoteDescription(new RTCSessionDescription(answer));
    } catch (err) {
      setError(err.message);
    }
  };

  const connectWebSocket = () => {
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`✅ WebSocket connected`);
    };

    ws.onmessage = (event) => {
      try {
        const data = event.data;
        if (data === "ping") {
          ws.send("pong");
          return;
        }
        if (data === "pong") return;

        const message = JSON.parse(data);
        console.log("📨 WebSocket message:", message); // DEBUG

        if (message.type === "detections") {
          lastDetectionsRef.current = message.data;
          setDetections(message.data);
          lastDetectionTimeRef.current = Date.now();

          // Tự động điền biển số vào input khi có text
          const detectionWithText = message.data.find((det) => det.text);

          console.log("🔍 Detection with text:", detectionWithText); // DEBUG
          console.log("🔍 userEdited:", userEdited); // DEBUG

          if (detectionWithText) {
            // ✅ Đọc được text
            if (!userEdited) {
              console.log("✅ Auto-filling:", detectionWithText.text); // DEBUG
              setPlateText(detectionWithText.text);
              setPlateSource("auto");
              setPlateConfidence(detectionWithText.confidence);
            } else {
              console.log("⚠️ Blocked by userEdited flag"); // DEBUG
            }
            setCannotReadPlate(false);
          } else if (message.data.length > 0) {
            // ❌ Có detection nhưng không có text (OCR chưa chạy frame này)
            // KHÔNG XÓA TEXT - giữ nguyên text cũ cho đến khi xe đi khỏi
            console.log("⚠️ Detection without text (frame skip)"); // DEBUG
            // Chỉ show warning nếu CHƯA BAO GIỜ có text
            if (!plateText) {
              setCannotReadPlate(true);
            }
          }
        }
      } catch (err) {
        console.error("❌ WebSocket error:", err); // DEBUG
      }
    };

    ws.onerror = (error) => {
      console.error(`❌ WebSocket error:`, error);
    };

    ws.onclose = () => {
      console.log(`🔌 WebSocket closed, reconnecting...`);
      setTimeout(connectWebSocket, 3000);
    };

    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 5000);

    ws.addEventListener("close", () => {
      clearInterval(pingInterval);
    });
  };

  const startDrawLoop = () => {
    const draw = () => {
      drawDetections();
      animationFrameRef.current = requestAnimationFrame(draw);
    };
    draw();
  };

  const drawDetections = () => {
    const canvas = canvasRef.current;
    const video = videoRef.current;

    if (!canvas || !video || video.videoWidth === 0) return;

    const ctx = canvas.getContext("2d");

    // DEBUG: Log dimensions
    if (lastDetectionsRef.current.length > 0) {
      console.log(`📐 Video: ${video.videoWidth}x${video.videoHeight}, Canvas: ${canvas.width}x${canvas.height}`);
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Xóa detections sau 1 giây không nhận được update (xe đã đi khỏi)
    const now = Date.now();
    if (now - lastDetectionTimeRef.current > 1000) {
      lastDetectionsRef.current = [];
      setDetections([]);
      setCannotReadPlate(false);

      // XÓA TEXT khi xe đi khỏi (nếu chưa user edit)
      if (!userEdited) {
        setPlateText("");
        setPlateSource("");
        setPlateConfidence(0);
      }

      return;
    }

    const currentDetections = lastDetectionsRef.current;

    currentDetections.forEach((detection) => {
      const [x, y, w, h] = detection.bbox;
      console.log(`📦 BBox: x=${x}, y=${y}, w=${w}, h=${h}`);

      let label = detection.class;
      if (detection.text) {
        label = `${detection.class}: ${detection.text}`;
      }
      label += ` (${(detection.confidence * 100).toFixed(0)}%)`;

      const color = detection.text ? "#00FF00" : "#0000FF";

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      ctx.font = "bold 12px Arial";
      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = color;
      ctx.fillRect(x, y - 20, textWidth + 10, 20);

      ctx.fillStyle = "#FFFFFF";
      ctx.fillText(label, x + 5, y - 5);
    });
  };

  const handleOpenBarrier = async () => {
    if (!plateText.trim()) {
      alert("Vui lòng nhập biển số!");
      return;
    }

    setIsOpening(true);

    try {
      const response = await fetch(`${backendUrl}/api/open-barrier`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plate_text: plateText.toUpperCase(),
          confidence: plateConfidence,
          source: plateSource || "manual",
        }),
      });

      const result = await response.json();

      if (result.success) {
        const action = result.action === "ENTRY" ? "VÀO" : "RA";
        alert(`✅ ${result.message}`);

        // Reset form
        setPlateText("");
        setPlateSource("");
        setCannotReadPlate(false);
        setUserEdited(false);

        // Notify parent để refresh history
        if (onHistoryUpdate) {
          onHistoryUpdate();
        }
      } else {
        alert(`❌ ${result.error}`);
      }
    } catch (error) {
      alert(`❌ Lỗi kết nối: ${error.message}`);
    } finally {
      setIsOpening(false);
    }
  };

  const cleanup = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    if (pcRef.current) pcRef.current.close();
    if (wsRef.current) wsRef.current.close();
  };

  return (
    <div className="card shadow-sm h-100 d-flex flex-column">
      {/* Header */}
      <div className="card-header bg-primary text-white d-flex justify-content-between align-items-center py-2 px-3">
        <h6 className="mb-0 small">
          <i className="bi bi-camera-video-fill me-1"></i>
          {cameraInfo ? cameraInfo.name : "Camera"}
        </h6>
        <div className="d-flex align-items-center gap-2">
          {cameraInfo && (
            <span className={`badge ${cameraInfo.type === 'ENTRY' ? 'bg-success' : 'bg-danger'}`}>
              {cameraInfo.type === 'ENTRY' ? 'VÀO' : 'RA'}
            </span>
          )}
          {isConnected ? (
            <i className="bi bi-circle-fill text-success fs-6"></i>
          ) : (
            <i className="bi bi-circle-fill text-secondary fs-6"></i>
          )}
        </div>
      </div>

      {/* Video */}
      <div className="card-body p-0" style={{ flex: "1 1 auto", minHeight: 0, overflow: "hidden" }}>
        <div className="position-relative bg-black h-100">
          {/* Loading Skeleton */}
          {!isVideoLoaded && (
            <div
              className="position-absolute top-0 start-0 w-100 h-100 d-flex flex-column align-items-center justify-content-center"
              style={{ backgroundColor: "#1a1a1a", zIndex: 10 }}
            >
              <div
                className="spinner-border text-primary mb-3"
                role="status"
                style={{ width: "3rem", height: "3rem" }}
              >
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          )}

          {/* Video */}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-100 h-100 d-block"
            style={{
              objectFit: "fill",
              opacity: isVideoLoaded ? 1 : 0,
              transition: "opacity 0.3s ease-in-out",
            }}
            onLoadedMetadata={(e) => {
              if (canvasRef.current) {
                canvasRef.current.width = e.target.videoWidth;
                canvasRef.current.height = e.target.videoHeight;
              }
            }}
          />

          {/* Canvas */}
          <canvas
            ref={canvasRef}
            className="position-absolute top-0 start-0"
            style={{
              pointerEvents: "none",
              width: "100%",
              height: "100%",
              imageRendering: "crisp-edges",
              opacity: isVideoLoaded ? 1 : 0,
              transition: "opacity 0.3s ease-in-out",
            }}
          />

          {/* Warning overlay - KHÔNG ảnh hưởng layout */}
          {cannotReadPlate && (
            <div
              className="position-absolute top-0 start-0 m-2 alert alert-warning py-1 px-2 small"
              style={{ zIndex: 20 }}
            >
              <i className="bi bi-exclamation-triangle-fill me-1"></i>
              Không đọc được biển số, vui lòng nhập tay
            </div>
          )}
        </div>
      </div>

      {/* Footer - Thông tin xe (Form cố định) */}
      <div className="card-footer bg-light p-3">
        <h6 className="mb-3 text-primary">
          <i className="bi bi-info-circle-fill me-1"></i>
          Thông tin xe
        </h6>

        {/* Biển số */}
        <div className="mb-2">
          <label className="form-label small mb-1 text-secondary">
            <i className="bi bi-hash me-1"></i>Biển số xe
          </label>
          <div className="input-group input-group-sm">
            <input
              type="text"
              value={plateText}
              onChange={(e) => {
                setPlateText(e.target.value);
                setUserEdited(true);
                if (plateSource === "auto") {
                  setPlateSource("manual");
                }
              }}
              className="form-control text-center fw-bold text-uppercase"
              placeholder="Chờ quét hoặc nhập tay..."
              style={{ fontSize: "1rem", letterSpacing: "1.5px" }}
            />
            {plateSource === "auto" && (
              <span className="input-group-text bg-info text-white px-2">
                <i className="bi bi-robot"></i>
              </span>
            )}
            {plateSource === "manual" && (
              <span className="input-group-text bg-warning text-dark px-2">
                <i className="bi bi-pencil-fill"></i>
              </span>
            )}
          </div>
        </div>

        {/* Ngày giờ */}
        <div className="mb-2">
          <label className="form-label small mb-1 text-secondary">
            <i className="bi bi-clock me-1"></i>Thời gian
          </label>
          <input
            type="text"
            className="form-control form-control-sm text-center"
            value={currentTime.toLocaleString('vi-VN', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit'
            })}
            disabled
            style={{ backgroundColor: '#e9ecef', fontSize: "0.9rem" }}
          />
        </div>

        {/* Loại camera */}
        <div className="mb-2">
          <label className="form-label small mb-1 text-secondary">
            <i className="bi bi-camera-video me-1"></i>Camera
          </label>
          <input
            type="text"
            className="form-control form-control-sm text-center"
            value={cameraInfo ? `${cameraInfo.name} (${cameraInfo.type === 'ENTRY' ? 'VÀO' : 'RA'})` : 'Đang tải...'}
            disabled
            style={{ backgroundColor: '#e9ecef', fontSize: "0.9rem" }}
          />
        </div>

        {/* Độ chính xác (luôn hiển thị) */}
        <div className="mb-2">
          <label className="form-label small mb-1 text-secondary">
            <i className="bi bi-speedometer2 me-1"></i>Độ chính xác
          </label>
          <div className="progress" style={{ height: "20px" }}>
            <div
              className={`progress-bar ${plateConfidence > 0.8 ? 'bg-success' : plateConfidence > 0.6 ? 'bg-warning' : 'bg-secondary'}`}
              role="progressbar"
              style={{ width: `${plateConfidence * 100}%` }}
            >
              {(plateConfidence * 100).toFixed(0)}%
            </div>
          </div>
        </div>

        {/* Nút mở cửa */}
        <button
          className={`btn w-100 mt-2 ${cameraInfo?.type === 'ENTRY' ? 'btn-success' : 'btn-danger'}`}
          onClick={handleOpenBarrier}
          disabled={isOpening || !plateText.trim()}
          style={{ fontSize: "1rem", padding: "10px" }}
        >
          {isOpening ? (
            <>
              <span className="spinner-border spinner-border-sm me-2"></span>
              Đang mở cửa...
            </>
          ) : (
            <>
              <i className="bi bi-door-open-fill me-2"></i>
              Mở cửa {cameraInfo?.type === 'ENTRY' ? 'VÀO' : 'RA'}
            </>
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="card-footer bg-danger text-white p-2 text-center">
          <small>
            <i className="bi bi-exclamation-triangle-fill me-1"></i>
            {error}
          </small>
        </div>
      )}
    </div>
  );
};

// ==================== History Panel ====================
const HistoryPanel = ({ backendUrl }) => {
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all"); // all | today | in | out

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();

      if (filter === "today") {
        params.append("today_only", "true");
      } else if (filter === "in") {
        params.append("status", "IN");
      } else if (filter === "out") {
        params.append("status", "OUT");
      }

      const response = await fetch(`${backendUrl}/api/history?${params}`);
      const data = await response.json();

      if (data.success) {
        setHistory(data.history);
        setStats(data.stats);
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    const interval = setInterval(fetchHistory, 10000); // Refresh mỗi 10s
    return () => clearInterval(interval);
  }, [filter]);

  return (
    <div className="card shadow-sm h-100">
      {/* Header */}
      <div className="card-header bg-dark text-white py-2 px-3">
        <div className="d-flex justify-content-between align-items-center">
          <h6 className="mb-0">
            <i className="bi bi-clock-history me-1"></i>
            Lịch sử
          </h6>
          <button
            className="btn btn-sm btn-outline-light"
            onClick={fetchHistory}
            disabled={loading}
          >
            <i className={`bi bi-arrow-clockwise ${loading ? 'spin' : ''}`}></i>
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="card-body p-2 bg-light border-bottom">
          <div className="row g-2 text-center small">
            <div className="col">
              <div className="fw-bold text-primary">{stats.today_in}</div>
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>VÀO</div>
            </div>
            <div className="col">
              <div className="fw-bold text-danger">{stats.today_out}</div>
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>RA</div>
            </div>
            <div className="col">
              <div className="fw-bold text-warning">{stats.vehicles_inside}</div>
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>Trong bãi</div>
            </div>
            <div className="col">
              <div className="fw-bold text-success">{(stats.today_fee / 1000).toFixed(0)}K</div>
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>Doanh thu</div>
            </div>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="px-2 pt-2">
        <div className="btn-group btn-group-sm w-100" role="group">
          <button
            className={`btn ${filter === 'all' ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => setFilter('all')}
          >
            Tất cả
          </button>
          <button
            className={`btn ${filter === 'today' ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => setFilter('today')}
          >
            Hôm nay
          </button>
          <button
            className={`btn ${filter === 'in' ? 'btn-success' : 'btn-outline-success'}`}
            onClick={() => setFilter('in')}
          >
            VÀO
          </button>
          <button
            className={`btn ${filter === 'out' ? 'btn-danger' : 'btn-outline-danger'}`}
            onClick={() => setFilter('out')}
          >
            RA
          </button>
        </div>
      </div>

      {/* History List */}
      <div className="flex-grow-1 overflow-auto p-2">
        {loading ? (
          <div className="text-center py-4">
            <div className="spinner-border spinner-border-sm text-primary"></div>
          </div>
        ) : history.length === 0 ? (
          <div className="text-center text-muted py-4 small">
            <i className="bi bi-inbox"></i>
            <div>Chưa có dữ liệu</div>
          </div>
        ) : (
          <div className="list-group list-group-flush">
            {history.map((entry) => (
              <div key={entry.id} className="list-group-item p-2 small">
                <div className="d-flex justify-content-between align-items-start">
                  <div>
                    <div className="fw-bold text-primary">{entry.plate_view}</div>
                    <div className="text-muted" style={{ fontSize: "0.7rem" }}>
                      <i className="bi bi-arrow-down-circle text-success me-1"></i>
                      {entry.entry_time}
                      {entry.entry_camera_name && (
                        <span className="ms-1">({entry.entry_camera_name})</span>
                      )}
                    </div>
                    {entry.exit_time && (
                      <div className="text-muted" style={{ fontSize: "0.7rem" }}>
                        <i className="bi bi-arrow-up-circle text-danger me-1"></i>
                        {entry.exit_time}
                        {entry.exit_camera_name && (
                          <span className="ms-1">({entry.exit_camera_name})</span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="text-end">
                    <span className={`badge ${entry.status === 'IN' ? 'bg-success' : 'bg-secondary'}`}>
                      {entry.status}
                    </span>
                    {entry.duration && (
                      <div className="text-muted mt-1" style={{ fontSize: "0.7rem" }}>
                        {entry.duration}
                      </div>
                    )}
                    {entry.fee > 0 && (
                      <div className="fw-bold text-success mt-1" style={{ fontSize: "0.75rem" }}>
                        {entry.fee.toLocaleString()}đ
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ==================== Main App ====================
const App1 = () => {
  const BACKEND_URL = "http://192.168.0.144:5000";
  const WS_URL = "ws://192.168.0.144:5000/ws/detections";

  const [historyKey, setHistoryKey] = useState(0);
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  const handleHistoryUpdate = () => {
    // Trigger history refresh
    setHistoryKey(prev => prev + 1);
  };

  return (
    <div
      className="d-flex flex-column"
      style={{
        width: "100vw",
        height: "100vh",
        overflow: "hidden",
        margin: 0,
        padding: 0,
      }}
    >
      {/* Header với nút lịch sử */}
      <div className="bg-primary text-white p-2 d-flex justify-content-between align-items-center">
        <h5 className="mb-0">
          <i className="bi bi-camera-video-fill me-2"></i>
          Hệ thống quản lý bãi xe
        </h5>
        <button
          className="btn btn-light btn-sm"
          onClick={() => setShowHistoryModal(true)}
        >
          <i className="bi bi-clock-history me-1"></i>
          Xem lịch sử
        </button>
      </div>

      {/* Camera Grid - NO SCROLL, fit trong viewport */}
      <div className="flex-grow-1 p-2 overflow-hidden">
        <div className="row g-2 h-100">
          {/* Camera 1 - có thể thêm nhiều camera sau */}
          <div className="col-12 col-md-6 col-lg-4 h-100">
            <CameraView
              backendUrl={BACKEND_URL}
              wsUrl={WS_URL}
              onHistoryUpdate={handleHistoryUpdate}
            />
          </div>

          {/* Placeholder cho Camera 2, 3... */}
          {/* Sau này uncomment để add thêm camera:
          <div className="col-12 col-md-6 col-lg-4 h-100">
            <CameraView
              backendUrl="http://192.168.0.145:5000"
              wsUrl="ws://192.168.0.145:5000/ws/detections"
              onHistoryUpdate={handleHistoryUpdate}
            />
          </div>
          */}
        </div>
      </div>

      {/* Modal lịch sử */}
      {showHistoryModal && (
        <div
          className="modal show d-block"
          style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
          onClick={() => setShowHistoryModal(false)}
        >
          <div
            className="modal-dialog modal-xl modal-dialog-scrollable"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-content">
              <div className="modal-header bg-primary text-white">
                <h5 className="modal-title">
                  <i className="bi bi-clock-history me-2"></i>
                  Lịch sử xe vào/ra
                </h5>
                <button
                  type="button"
                  className="btn-close btn-close-white"
                  onClick={() => setShowHistoryModal(false)}
                ></button>
              </div>
              <div className="modal-body p-0" style={{ height: "70vh" }}>
                <HistoryPanel
                  key={historyKey}
                  backendUrl={BACKEND_URL}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App1;
