import { useEffect, useRef, useState } from "react";
import type { Camera } from "../types/camera";
import { go2rtcApi } from "../services/go2rtcApi";
import "./VideoPlayer.css";

interface VideoPlayerProps {
  camera: Camera;
  onRemove?: (cameraId: string) => void;
  onEdit?: (camera: Camera) => void;
  enableDetection?: boolean; // Toggle detection on/off
}

export const VideoPlayerWithDetection = ({
  camera,
  onRemove,
  onEdit,
  enableDetection = true,
}: VideoPlayerProps) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const streamSetRef = useRef(false);
  const detectionWsRef = useRef<WebSocket | null>(null);

  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [lastDetectionTime, setLastDetectionTime] = useState(0);
  const [detectionCount, setDetectionCount] = useState(0);
  const [detections, setDetections] = useState<any[]>([]);

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.25, 5));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.25, 0.5));
  const handleResetZoom = () => setZoom(1);

  const handleFullscreen = () => {
    if (containerRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        containerRef.current.requestFullscreen();
      }
    }
  };

  // Connect to detection WebSocket
  useEffect(() => {
    if (!enableDetection) return;

    const wsUrl = `ws://localhost:5000/ws/detections`;
    const ws = new WebSocket(wsUrl);
    detectionWsRef.current = ws;

    ws.onopen = () => {
      console.log("[Detection WS] Connected");

      // Stop first (in case camera is already running), then start
      fetch(`http://localhost:5000/api/detection/stop/${camera.id}`, {
        method: "POST",
      })
        .catch(() => {
          // Ignore if camera wasn't running
        })
        .finally(() => {
          // Start detection for this camera
          // Backend will automatically lookup RTSP URL from camera ID
          fetch(
            `http://localhost:5000/api/detection/start/${camera.id}?conf_threshold=0.25`,
            { method: "POST" }
          )
            .then((res) => res.json())
            .then((data) => console.log("[Detection] Started:", data))
            .catch((err) => console.error("[Detection] Failed to start:", err));
        });
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Backend gửi detection coordinates - lưu vào state
        if (data.detections && data.camera_id === camera.id) {
          const dets = data.detections || [];

          console.log("[Detection WS] Received detections:", dets.length, dets);

          setDetections(dets);

          // Update detection stats
          if (dets.length > 0) {
            setLastDetectionTime(Date.now());
            setDetectionCount((prev) => prev + dets.length);
          }
        }
      } catch (err) {
        console.error("[Detection WS] Parse error:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("[Detection WS] Error:", err);
    };

    ws.onclose = () => {
      console.log("[Detection WS] Closed");
    };

    return () => {
      // Stop detection
      fetch(`http://localhost:5000/api/detection/stop/${camera.id}`, {
        method: "POST",
      }).catch((err) => console.error("[Detection] Failed to stop:", err));

      if (ws) {
        ws.close();
      }
    };
  }, [enableDetection, camera.id, camera.url]);

  // Draw detections continuously
  useEffect(() => {
    if (!enableDetection) return;

    let animationId: number;

    const drawLoop = () => {
      const canvas = canvasRef.current;
      const video = videoRef.current;

      if (!canvas || !video || video.videoWidth === 0) {
        animationId = requestAnimationFrame(drawLoop);
        return;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      // Match canvas size to video
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
      }

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Check if detections are recent (within 1 second)
      const now = Date.now();
      if (now - lastDetectionTime > 1000 || detections.length === 0) {
        animationId = requestAnimationFrame(drawLoop);
        return;
      }

      console.log("[Canvas] Drawing", detections.length, "detections on canvas", canvas.width, "x", canvas.height);

      // Draw each detection
      detections.forEach((det: any) => {
        const [x, y, w, h] = det.bbox;
        const label = `${det.class} ${(det.confidence * 100).toFixed(0)}%`;

        console.log("[Canvas] Drawing box at", x, y, w, h, "label:", label);

        // Draw box
        ctx.strokeStyle = "#00FF00";
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, w, h);

        // Draw label background
        ctx.font = "bold 16px Arial";
        const textWidth = ctx.measureText(label).width;
        ctx.fillStyle = "#00FF00";
        ctx.fillRect(x, y - 25, textWidth + 10, 25);

        // Draw label text
        ctx.fillStyle = "#000000";
        ctx.fillText(label, x + 5, y - 5);
      });

      animationId = requestAnimationFrame(drawLoop);
    };

    drawLoop();

    return () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
    };
  }, [detections, lastDetectionTime, enableDetection]);

  // WebRTC Video Stream (same as original)
  useEffect(() => {
    let ws: WebSocket | null = null;

    const startStream = async () => {
      try {
        setLoading(true);
        setError("");

        const pc = new RTCPeerConnection({
          iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
        });
        pcRef.current = pc;

        pc.ontrack = (event) => {
          if (videoRef.current && event.streams[0] && !streamSetRef.current) {
            streamSetRef.current = true;
            const video = videoRef.current;
            video.srcObject = event.streams[0];
            video.setAttribute("playsinline", "true");

            const tryPlay = () => {
              video
                .play()
                .then(() => {
                  setLoading(false);
                  if (video.buffered.length > 0) {
                    const latency = video.currentTime - video.buffered.start(0);
                    if (latency > 0.5) {
                      video.currentTime = video.buffered.end(0) - 0.1;
                    }
                  }
                })
                .catch(() => setLoading(false));
            };

            video.onloadedmetadata = () => tryPlay();
            if (video.readyState >= 1) tryPlay();
            video.onerror = () => {
              setError(`Video error: ${video.error?.message || "Unknown"}`);
              setLoading(false);
            };
            video.onplaying = () => setLoading(false);
          }
        };

        pc.oniceconnectionstatechange = () => {
          if (
            pc.iceConnectionState === "failed" ||
            pc.iceConnectionState === "disconnected"
          ) {
            setError(`Connection ${pc.iceConnectionState}`);
            setLoading(false);
          }
        };

        pc.onconnectionstatechange = () => {
          if (pc.connectionState === "failed") {
            setError("Connection failed");
            setLoading(false);
          }
        };

        pc.addTransceiver("video", { direction: "recvonly" });
        pc.addTransceiver("audio", { direction: "recvonly" });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const wsUrl = go2rtcApi.getStreamUrl(camera.url);
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          ws?.send(
            JSON.stringify({
              type: "webrtc/offer",
              value: offer.sdp,
            })
          );
        };

        ws.onmessage = async (event) => {
          const msg = JSON.parse(event.data);

          if (msg.type === "webrtc/answer") {
            await pc.setRemoteDescription({
              type: "answer",
              sdp: msg.value,
            });
          } else if (msg.type === "webrtc/candidate") {
            try {
              await pc.addIceCandidate(
                new RTCIceCandidate({
                  candidate: msg.value,
                  sdpMid: "0",
                })
              );
            } catch (err) {
              // Ignore
            }
          } else if (msg.type === "error") {
            setError(msg.value || "Stream error");
            setLoading(false);
          }
        };

        ws.onerror = () => {
          setError("WebSocket connection failed");
          setLoading(false);
        };

        ws.onclose = (event) => {
          if (event.code !== 1000) {
            setError(`Connection closed: ${event.reason || "Unknown error"}`);
            setLoading(false);
          }
        };
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start stream");
        setLoading(false);
      }
    };

    startStream();

    return () => {
      streamSetRef.current = false;
      if (ws) ws.close();
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
    };
  }, [camera.url]);

  return (
    <div className="card bg-dark text-white h-100">
      <div className="card-header d-flex justify-content-between align-items-center">
        <h5 className="card-title mb-0">{camera.name}</h5>
        <div className="d-flex gap-2 align-items-center">
          {enableDetection && (
            <span className="badge bg-success">
              <i className="bi bi-eye me-1"></i>
              Detection: {detectionCount}
            </span>
          )}
          {onEdit && (
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => onEdit(camera)}
              title="Edit camera settings"
            >
              <i className="bi bi-gear"></i>
            </button>
          )}
          {onRemove && (
            <button
              className="btn btn-sm btn-danger"
              onClick={() => onRemove(camera.id)}
              title="Remove camera"
            >
              <i className="bi bi-x-lg"></i>
            </button>
          )}
        </div>
      </div>

      <div
        ref={containerRef}
        className="card-body p-0 position-relative video-container"
        style={{ "--video-zoom": zoom } as React.CSSProperties}
      >
        {loading && (
          <div className="position-absolute top-50 start-50 translate-middle">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="position-absolute top-50 start-50 translate-middle w-75">
            <div className="alert alert-danger mb-0" role="alert">
              <i className="bi bi-exclamation-triangle me-2"></i>
              {error}
            </div>
          </div>
        )}

        {/* Video element */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="position-absolute top-0 start-0 w-100 h-100 video-element"
          style={{ objectFit: "contain" }}
        />

        {/* Canvas overlay for detections */}
        {enableDetection && (
          <canvas
            ref={canvasRef}
            className="position-absolute top-0 start-0 w-100 h-100"
            style={{ pointerEvents: "none", objectFit: "contain" }}
          />
        )}

        {/* Custom Controls */}
        <div className="position-absolute bottom-0 start-0 w-100 video-controls p-2">
          <div className="d-flex justify-content-between align-items-center">
            <div className="btn-group" role="group">
              <button
                className="btn btn-sm btn-dark"
                onClick={handleZoomOut}
                disabled={zoom <= 1}
                title="Zoom Out"
              >
                <i className="bi bi-zoom-out"></i>
              </button>
              <button
                className="btn btn-sm btn-dark"
                onClick={handleResetZoom}
                disabled={zoom === 1}
                title="Reset Zoom"
              >
                {Math.round(zoom * 100)}%
              </button>
              <button
                className="btn btn-sm btn-dark"
                onClick={handleZoomIn}
                disabled={zoom >= 5}
                title="Zoom In"
              >
                <i className="bi bi-zoom-in"></i>
              </button>
            </div>

            <button
              className="btn btn-sm btn-dark"
              onClick={handleFullscreen}
              title="Fullscreen"
            >
              <i className="bi bi-fullscreen"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
