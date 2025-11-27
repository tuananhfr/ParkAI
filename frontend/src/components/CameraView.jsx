import { useEffect, useRef, useState } from "react";
import { CENTRAL_URL } from "../config";

const formatTime = (date) =>
  date.toLocaleString("vi-VN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

const CameraView = ({ camera, onHistoryUpdate }) => {
  const streamProxy = camera?.stream_proxy;
  const controlProxy = camera?.control_proxy;

  const wantsAnnotated =
    streamProxy?.default_mode === "annotated" &&
    streamProxy?.supports_annotated !== false;

  const containerRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const peerRef = useRef(null);
  const wsRef = useRef(null);
  const animationFrameRef = useRef(null);
  const lastDetectionsRef = useRef([]);
  const lastDetectionTimeRef = useRef(0);
  const retryRef = useRef(null);
  const userEditedRef = useRef(false);
  const plateTextRef = useRef("");

  const [isConnected, setIsConnected] = useState(false);
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [detections, setDetections] = useState([]);
  const [plateText, setPlateText] = useState("");
  const [plateSource, setPlateSource] = useState("");
  const [plateConfidence, setPlateConfidence] = useState(0);
  const [cannotReadPlate, setCannotReadPlate] = useState(false);
  const [isOpening, setIsOpening] = useState(false);
  const [cameraInfo, setCameraInfo] = useState({
    name: camera?.name,
    type: camera?.type,
    location: camera?.location,
  });
  const [userEdited, setUserEdited] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    setCameraInfo({
      name: camera?.name,
      type: camera?.type,
      location: camera?.location,
    });
  }, [camera?.name, camera?.type, camera?.location]);

  useEffect(() => {
    userEditedRef.current = userEdited;
  }, [userEdited]);

  useEffect(() => {
    plateTextRef.current = plateText;
  }, [plateText]);

  useEffect(() => {
    const interval = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const draw = () => {
      drawDetections();
      animationFrameRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;

    cleanupRetry();
    cleanupPeer();
    cleanupVideo();

    if (!camera || camera.status !== "online") {
      setIsConnected(false);
      setIsVideoLoaded(false);
      setError("Camera chưa online");
      return () => {
        cancelled = true;
        cleanupPeer();
        cleanupVideo();
      };
    }

    if (!streamProxy?.available) {
      setError(streamProxy?.reason || "Chưa cấu hình stream proxy");
      setIsConnected(false);
      setIsVideoLoaded(false);
      return () => {
        cancelled = true;
      };
    }

    const endpoint = `${CENTRAL_URL}/api/cameras/${camera.id}/offer${
      wantsAnnotated ? "?annotated=true" : ""
    }`;

    const startStream = async () => {
      if (cancelled) return;

      setError(null);
      setIsVideoLoaded(false);

      const pc = new RTCPeerConnection({
        iceServers: [{ urls: ["stun:stun.l.google.com:19302"] }],
      });

      pc.addTransceiver("video", { direction: "recvonly" });
      peerRef.current = pc;

      pc.ontrack = (event) => {
        if (!videoRef.current) return;
        const [stream] = event.streams;
        videoRef.current.srcObject = stream || new MediaStream([event.track]);
        setIsConnected(true);

        videoRef.current.onloadeddata = () => {
          if (!cancelled) {
            setIsVideoLoaded(true);
          }
        };
      };

      pc.onconnectionstatechange = () => {
        if (["failed", "closed"].includes(pc.connectionState)) {
          setIsConnected(false);
          scheduleReconnect();
        }
      };

      try {
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sdp: offer.sdp,
            type: offer.type,
          }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const answer = await response.json();
        await pc.setRemoteDescription(answer);
      } catch (err) {
        console.error("WebRTC error:", err);
        setError(
          err?.message ||
            "Không thể kết nối WebRTC. Vui lòng kiểm tra Edge camera."
        );
        setIsConnected(false);
        scheduleReconnect();
      }
    };

    const scheduleReconnect = (delay = 4000) => {
      if (cancelled) return;
      cleanupPeer();
      cleanupVideo();
      if (retryRef.current) return;
      retryRef.current = setTimeout(() => {
        retryRef.current = null;
        startStream();
      }, delay);
    };

    startStream();

    return () => {
      cancelled = true;
      cleanupRetry();
      cleanupPeer();
      cleanupVideo();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    camera?.id,
    camera?.status,
    streamProxy?.available,
    streamProxy?.default_mode,
    streamProxy?.supports_annotated,
    wantsAnnotated,
  ]);

  useEffect(() => {
    cleanupWebSocket();

    if (!controlProxy?.ws_url) {
      lastDetectionsRef.current = [];
      setDetections([]);
      return;
    }

    const ws = new WebSocket(controlProxy.ws_url);
    wsRef.current = ws;

    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 5000);

    ws.onopen = () => {
      console.log("✅ WebSocket connected:", controlProxy.ws_url);
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
          lastDetectionsRef.current = message.data || [];
          setDetections(message.data || []);
          lastDetectionTimeRef.current = Date.now();

          const detectionWithText = (message.data || []).find(
            (det) => det.text
          );

          if (detectionWithText) {
            if (!userEditedRef.current) {
              setPlateText(detectionWithText.text);
              setPlateSource("auto");
              setPlateConfidence(detectionWithText.confidence || 0);
            }
            setCannotReadPlate(false);
          } else if ((message.data || []).length > 0) {
            if (!plateTextRef.current) {
              setCannotReadPlate(true);
            }
          }
        }
      } catch (err) {
        console.error("❌ WebSocket error:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("❌ WebSocket error:", err);
    };

    ws.onclose = () => {
      clearInterval(pingInterval);
      setTimeout(() => {
        if (wsRef.current === ws) {
          cleanupWebSocket();
        }
      }, 0);
    };

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [controlProxy?.ws_url, camera?.id]);

  const cleanupPeer = () => {
    if (peerRef.current) {
      peerRef.current.ontrack = null;
      peerRef.current.onconnectionstatechange = null;
      peerRef.current.close();
      peerRef.current = null;
    }
  };

  const cleanupVideo = () => {
    if (videoRef.current?.srcObject) {
      const tracks = videoRef.current.srcObject.getTracks();
      tracks.forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setIsVideoLoaded(false);
  };

  const cleanupRetry = () => {
    if (retryRef.current) {
      clearTimeout(retryRef.current);
      retryRef.current = null;
    }
  };

  const cleanupWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  };

  const drawDetections = () => {
    const canvas = canvasRef.current;
    const video = videoRef.current;

    if (!canvas || !video || video.videoWidth === 0) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const now = Date.now();
    if (now - lastDetectionTimeRef.current > 1000) {
      lastDetectionsRef.current = [];
      if (!userEditedRef.current) {
        setPlateText("");
        setPlateSource("");
        setPlateConfidence(0);
      }
      setDetections([]);
      setCannotReadPlate(false);
      return;
    }

    lastDetectionsRef.current.forEach((detection) => {
      const [x, y, w, h] = detection.bbox;
      let label = detection.class;
      if (detection.text) {
        label = `${detection.class}: ${detection.text}`;
      }
      label += ` (${((detection.confidence || 0) * 100).toFixed(0)}%)`;

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

    if (!controlProxy?.open_barrier_url) {
      alert("Chưa cấu hình API mở barrier cho camera này.");
      return;
    }

    try {
      setIsOpening(true);
      const response = await fetch(controlProxy.open_barrier_url, {
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
        alert(result.message || "Đã mở cửa thành công");
        setPlateText("");
        setPlateSource("");
        setPlateConfidence(0);
        setCannotReadPlate(false);
        setUserEdited(false);
        userEditedRef.current = false;
        plateTextRef.current = "";

        if (typeof onHistoryUpdate === "function") {
          onHistoryUpdate();
        }
      } else {
        alert(result.error || "Không thể mở cửa");
      }
    } catch (err) {
      alert(`Lỗi kết nối: ${err.message}`);
    } finally {
      setIsOpening(false);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      const isCurrentFullscreen =
        document.fullscreenElement === containerRef.current;
      setIsFullscreen(isCurrentFullscreen);
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  const toggleFullscreen = async () => {
    const containerEl = containerRef.current;
    if (!containerEl) return;

    try {
      if (!document.fullscreenElement) {
        if (containerEl.requestFullscreen) {
          await containerEl.requestFullscreen();
        } else {
          setIsFullscreen(true);
        }
      } else if (document.exitFullscreen) {
        await document.exitFullscreen();
      } else {
        setIsFullscreen(false);
      }
    } catch (err) {
      console.error("Fullscreen error:", err);
      setIsFullscreen((prev) => !prev);
    }
  };

  return (
    <div
      ref={containerRef}
      className={`card shadow-sm d-flex flex-column ${
        isFullscreen ? "position-fixed top-0 start-0 w-100 h-100 z-3" : "h-100"
      }`}
      style={
        isFullscreen ? { backgroundColor: "#000", borderRadius: 0 } : undefined
      }
    >
      <div
        className={`card-header bg-primary text-white d-flex justify-content-between align-items-center py-2 px-3 ${
          isFullscreen ? "d-none" : ""
        }`}
      >
        <h6 className="mb-0 small">
          <i className="bi bi-camera-video-fill me-1"></i>
          {cameraInfo?.name || `Camera #${camera?.id}`}
        </h6>
        <div className="d-flex align-items-center gap-2">
          {cameraInfo && (
            <span
              className={`badge ${
                cameraInfo.type === "ENTRY" ? "bg-success" : "bg-danger"
              }`}
            >
              {cameraInfo.type === "ENTRY" ? "VÀO" : "RA"}
            </span>
          )}
          <i
            className={`bi bi-circle-fill fs-6 ${
              isConnected ? "text-success" : "text-secondary"
            }`}
          ></i>
        </div>
      </div>

      <div
        className="card-body p-0"
        style={{ flex: "1 1 auto", minHeight: 0, overflow: "hidden" }}
      >
        <div className="position-relative bg-black h-100">
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
          />

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

          {cannotReadPlate && (
            <div
              className="position-absolute top-0 start-0 m-2 alert alert-warning py-1 px-2 small"
              style={{ zIndex: 20 }}
            >
              <i className="bi bi-exclamation-triangle-fill me-1"></i>
              Không đọc được biển số, vui lòng nhập tay
            </div>
          )}

          <button
            type="button"
            className="btn btn-light btn-sm position-absolute"
            style={{ bottom: "10px", right: "10px", zIndex: 30, opacity: 0.9 }}
            onClick={toggleFullscreen}
            title={isFullscreen ? "Thu nhỏ" : "Phóng to"}
          >
            <i
              className={`bi ${
                isFullscreen ? "bi-fullscreen-exit" : "bi-fullscreen"
              }`}
            ></i>
          </button>
        </div>
      </div>

      <div
        className={`card-footer bg-light p-3 ${isFullscreen ? "d-none" : ""}`}
      >
        <h6 className="mb-3 text-primary">
          <i className="bi bi-info-circle-fill me-1"></i>
          Thông tin xe
        </h6>

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
                plateTextRef.current = e.target.value;
                setUserEdited(true);
                userEditedRef.current = true;
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

        <div className="mb-2">
          <label className="form-label small mb-1 text-secondary">
            <i className="bi bi-clock me-1"></i>Thời gian
          </label>
          <input
            type="text"
            className="form-control form-control-sm text-center"
            value={formatTime(currentTime)}
            disabled
            style={{ backgroundColor: "#e9ecef", fontSize: "0.9rem" }}
          />
        </div>

        <div className="mb-2">
          <label className="form-label small mb-1 text-secondary">
            <i className="bi bi-camera-video me-1"></i>Camera
          </label>
          <input
            type="text"
            className="form-control form-control-sm text-center"
            value={
              cameraInfo
                ? `${cameraInfo.name || "Camera"} (${
                    cameraInfo.type === "ENTRY" ? "VÀO" : "RA"
                  })`
                : "Đang tải..."
            }
            disabled
            style={{ backgroundColor: "#e9ecef", fontSize: "0.9rem" }}
          />
        </div>

        <div className="mb-2">
          <label className="form-label small mb-1 text-secondary">
            <i className="bi bi-speedometer2 me-1"></i>Độ chính xác
          </label>
          <div className="progress" style={{ height: "20px" }}>
            <div
              className={`progress-bar ${
                plateConfidence > 0.8
                  ? "bg-success"
                  : plateConfidence > 0.6
                  ? "bg-warning"
                  : "bg-secondary"
              }`}
              role="progressbar"
              style={{ width: `${Math.min(plateConfidence * 100, 100)}%` }}
            >
              {(plateConfidence * 100).toFixed(0)}%
            </div>
          </div>
        </div>

        <button
          className={`btn w-100 mt-2 ${
            cameraInfo?.type === "ENTRY" ? "btn-success" : "btn-danger"
          }`}
          onClick={handleOpenBarrier}
          disabled={
            isOpening || !plateText.trim() || !controlProxy?.open_barrier_url
          }
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
              Mở cửa {cameraInfo?.type === "ENTRY" ? "VÀO" : "RA"}
            </>
          )}
        </button>
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
  );
};

export default CameraView;
