import React, { useEffect, useState, useRef } from "react";

// ==================== Camera Component ====================
const CameraView = ({ cameraId, backendUrl, wsUrl }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [detections, setDetections] = useState([]);
  const [plateText, setPlateText] = useState("");
  const [plateStatus, setPlateStatus] = useState(null); // "IN" or "OUT"
  const [plateTime, setPlateTime] = useState(null); // Thời gian
  const [plateMessage, setPlateMessage] = useState(null); // Message đầy đủ
  const [barrierOpen, setBarrierOpen] = useState(false); // Barrier mở/đóng

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const pcRef = useRef(null);
  const wsRef = useRef(null);
  const animationFrameRef = useRef(null);
  const lastDetectionsRef = useRef([]);
  const barrierTimeoutRef = useRef(null); // Timeout để đóng barrier
  const lastPlateTextRef = useRef(""); // Track biển số hiện tại
  const lastDetectionTimeRef = useRef(0); // Track thời gian detection cuối

  useEffect(() => {
    startWebRTC();
    connectWebSocket();
    startDrawLoop();

    return () => {
      cleanup();
    };
  }, []);

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

          // Wait for video to actually start playing
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
      console.log(`✅ Camera ${cameraId} WebSocket connected`);
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

        if (message.type === "detections") {
          lastDetectionsRef.current = message.data;
          setDetections(message.data);
          lastDetectionTimeRef.current = Date.now(); // Cập nhật thời gian
        } else if (message.type === "plate_state") {
          // Nhận plate state từ WebSocket (real-time)
          const plateData = message.data;
          if (plateData.barrier_open && plateData.text) {
            console.log(`🚗 Camera ${cameraId} - ${plateData.message || plateData.text}`);
            setPlateText(plateData.text);
            setPlateStatus(plateData.status);
            setPlateTime(plateData.time);
            setPlateMessage(plateData.message);
            setBarrierOpen(true);
          } else if (!plateData.barrier_open && barrierOpen) {
            console.log(`🚪 Camera ${cameraId} - Barrier đóng (xe đã đi qua)`);
            setPlateText("");
            setPlateStatus(null);
            setPlateTime(null);
            setPlateMessage(null);
            setBarrierOpen(false);
          }
        }
      } catch (err) {
        // Silent fail
      }
    };

    ws.onerror = (error) => {
      console.error(`❌ Camera ${cameraId} WebSocket error:`, error);
    };

    ws.onclose = () => {
      console.log(`🔌 Camera ${cameraId} WebSocket closed, reconnecting...`);
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
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Xóa detections sau 2 giây không nhận được update
    const now = Date.now();
    if (now - lastDetectionTimeRef.current > 2000) {
      lastDetectionsRef.current = [];
      setDetections([]);
      return;
    }

    const currentDetections = lastDetectionsRef.current;

    currentDetections.forEach((detection) => {
      const [x, y, w, h] = detection.bbox;

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

  const cleanup = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    if (pcRef.current) pcRef.current.close();
    if (wsRef.current) wsRef.current.close();
  };

  return (
    <div className="col h-100">
      <div className="card shadow-sm h-100">
        <div className="card-header bg-white text-black d-flex justify-content-between align-items-center py-2 px-3">
          <h6 className="mb-0 small ">
            <i className="bi bi-camera-video-fill me-1"></i>
            Camera {cameraId}
          </h6>
          {isConnected ? (
            <i className="bi bi-circle-fill text-success fs-6"></i>
          ) : (
            <i className="bi bi-circle-fill text-secondary fs-6"></i>
          )}
        </div>

        <div className="card-body p-0 flex-grow-1 d-flex flex-column">
          <div className="position-relative bg-black flex-grow-1">
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
                objectFit: "contain",
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
          </div>
        </div>

        <div className="card-footer bg-light p-2">
          {barrierOpen ? (
            <>
              {/* Biển số */}
              <div className="input-group input-group-sm mb-2">
                <span className="input-group-text p-1">
                  <i className="bi bi-hash"></i>
                </span>
                <input
                  type="text"
                  value={plateText}
                  readOnly
                  className="form-control text-center fw-bold text-uppercase"
                  style={{ fontSize: "0.9rem", letterSpacing: "1px" }}
                />
              </div>

              {/* Status và Time */}
              {plateStatus && (
                <div className="d-flex justify-content-between align-items-center gap-2">
                  <span
                    className={`badge ${
                      plateStatus === "IN" ? "bg-success" : "bg-danger"
                    } flex-grow-1`}
                  >
                    <i
                      className={`bi ${
                        plateStatus === "IN"
                          ? "bi-box-arrow-in-right"
                          : "bi-box-arrow-right"
                      } me-1`}
                    ></i>
                    {plateStatus === "IN" ? "VÀO" : "RA"}
                  </span>
                  {plateTime && (
                    <span className="badge bg-secondary flex-grow-1 text-truncate small">
                      <i className="bi bi-clock me-1"></i>
                      {plateTime.split(" ")[1]}
                    </span>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="text-center text-muted small py-2">
              <i className="bi bi-hourglass-split me-1"></i>
              Chờ xe...
            </div>
          )}
        </div>

        {error && (
          <div className="card-footer bg-danger text-white p-2 text-center">
            <small>
              <i className="bi bi-exclamation-triangle-fill me-1"></i>
              {error}
            </small>
          </div>
        )}
      </div>
    </div>
  );
};

// ==================== Main App ====================
const App = () => {
  const BACKEND_URL = "http://192.168.0.144:5000";
  const WS_URL = "ws://192.168.0.144:5000/ws/detections";

  const TOTAL_CAMERAS = 4;
  const CAMERAS_PER_PAGE = 3;
  const TOTAL_PAGES = Math.ceil(TOTAL_CAMERAS / CAMERAS_PER_PAGE);

  const [currentPage, setCurrentPage] = useState(1);

  // Tính toán cameras hiển thị trên trang hiện tại
  const startIndex = (currentPage - 1) * CAMERAS_PER_PAGE;
  const endIndex = startIndex + CAMERAS_PER_PAGE;
  const currentCameras = Array.from(
    { length: TOTAL_CAMERAS },
    (_, i) => i + 1
  ).slice(startIndex, endIndex);

  const goToPrevious = () => {
    setCurrentPage((prev) => Math.max(1, prev - 1));
  };

  const goToNext = () => {
    setCurrentPage((prev) => Math.min(TOTAL_PAGES, prev + 1));
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
      {/* Cameras Grid - Responsive: Mobile 1, Tablet 2, Desktop 3 */}
      <div className="flex-grow-1 p-2" style={{ overflow: "hidden" }}>
        <div className="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-2 h-100 m-0">
          {currentCameras.map((id) => (
            <CameraView
              key={id}
              cameraId={id}
              backendUrl={BACKEND_URL}
              wsUrl={WS_URL}
            />
          ))}
          {/* Empty placeholders để giữ layout */}
          {Array.from({ length: CAMERAS_PER_PAGE - currentCameras.length }).map(
            (_, i) => (
              <div
                key={`placeholder-${i}`}
                className="col"
                style={{ minWidth: "0" }}
              ></div>
            )
          )}
        </div>
      </div>

      {/* Navigation Buttons - Fixed Bottom */}
      <div
        className="d-flex justify-content-center align-items-center gap-2 gap-md-3 px-2 py-2 bg-light border-top"
        style={{ height: "60px", flexShrink: 0 }}
      >
        <button
          className="btn btn-sm btn-primary d-flex align-items-center gap-1"
          onClick={goToPrevious}
          disabled={currentPage === 1}
        >
          <i className="bi bi-chevron-left"></i>
          <span className="d-none d-md-inline">Previous</span>
        </button>

        <div className="d-flex align-items-center gap-1">
          {Array.from({ length: TOTAL_PAGES }, (_, i) => i + 1).map((page) => (
            <button
              key={page}
              className={`btn btn-sm ${
                page === currentPage ? "btn-primary" : "btn-outline-primary"
              }`}
              onClick={() => setCurrentPage(page)}
            >
              {page}
            </button>
          ))}
        </div>

        <button
          className="btn btn-sm btn-primary d-flex align-items-center gap-1"
          onClick={goToNext}
          disabled={currentPage === TOTAL_PAGES}
        >
          <span className="d-none d-md-inline">Next</span>
          <i className="bi bi-chevron-right"></i>
        </button>

        <span className="badge bg-secondary ms-1 ms-md-3 small">
          {startIndex + 1}-{Math.min(endIndex, TOTAL_CAMERAS)} / {TOTAL_CAMERAS}
        </span>
      </div>
    </div>
  );
};

export default App;
