/**
 * CameraView - Component chính hiển thị camera và xử lý vào/ra
 * Đã được refactor để sử dụng các component và hooks nhỏ hơn
 */
import { useEffect, useRef, useState } from "react";
import { CENTRAL_URL } from "../config";
import { validatePlateNumber } from "../utils/plateValidation";

// Import components
import CameraHeader from "./CameraHeader";
import VideoStream from "./VideoStream";
import PlateImage from "./PlateImage";
import PlateInput from "./PlateInput";
import VehicleInfo from "./VehicleInfo";
import BarrierControls from "./BarrierControls";
import EditPlateModal from "./EditPlateModal";
import Notification from "./Notification";

const CameraView = ({ camera, onHistoryUpdate }) => {
  const streamProxy = camera?.stream_proxy;
  const controlProxy = camera?.control_proxy;

  const wantsAnnotated =
    streamProxy?.default_mode === "annotated" &&
    streamProxy?.supports_annotated !== false;

  // Refs
  const containerRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const peerRef = useRef(null);
  const wsRef = useRef(null);
  const retryRef = useRef(null);
  const userEditedRef = useRef(false);
  const plateTextRef = useRef("");
  const lastDetectionsRef = useRef([]);
  const lastDetectionTimeRef = useRef(0);

  // State
  const [isConnected, setIsConnected] = useState(false);
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [detections, setDetections] = useState([]);
  const [plateText, setPlateText] = useState("");
  const [plateSource, setPlateSource] = useState("");
  const [plateConfidence, setPlateConfidence] = useState(0);
  const [plateImage, setPlateImage] = useState(null);
  const [cannotReadPlate, setCannotReadPlate] = useState(false);
  const [plateValid, setPlateValid] = useState(true);
  const [isOpening, setIsOpening] = useState(false);
  const [cameraInfo, setCameraInfo] = useState({
    name: camera?.name,
    type: camera?.type,
    location: camera?.location,
  });
  const [userEdited, setUserEdited] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [barrierStatus, setBarrierStatus] = useState({
    is_open: false,
    enabled: false,
  });
  const [barrierOpenedPlate, setBarrierOpenedPlate] = useState(null);
  const [notificationMessage, setNotificationMessage] = useState(null);
  const [vehicleInfo, setVehicleInfo] = useState({
    entry_time: null,
    exit_time: null,
    fee: 0,
    duration: null,
    customer_type: null,
    is_subscriber: false,
  });
  const [showEditModal, setShowEditModal] = useState(false);

  // Update camera info when camera changes
  useEffect(() => {
    setCameraInfo({
      name: camera?.name,
      type: camera?.type,
      location: camera?.location,
    });
  }, [camera?.name, camera?.type, camera?.location]);

  // Sync refs with state
  useEffect(() => {
    userEditedRef.current = userEdited;
  }, [userEdited]);

  useEffect(() => {
    plateTextRef.current = plateText;
  }, [plateText]);

  // Fetch vehicle info when plate text changes
  useEffect(() => {
    const fetchVehicleInfo = async () => {
      if (!plateText || plateText.trim().length < 5) {
        setVehicleInfo({
          entry_time: null,
          exit_time: null,
          fee: 0,
          duration: null,
          customer_type: null,
          is_subscriber: false,
        });
        return;
      }

      try {
        const response = await fetch(
          `${CENTRAL_URL}/api/parking/history?limit=100&today_only=false`
        );
        const data = await response.json();

        if (data.success && data.history) {
          const normalizedPlate = plateText.trim().toUpperCase();
          const vehicle = data.history.find(
            (entry) =>
              entry.plate_id?.toUpperCase() === normalizedPlate ||
              entry.plate_view?.toUpperCase() === normalizedPlate ||
              entry.plate_view?.replace(/-/g, "").toUpperCase() ===
                normalizedPlate.replace(/-/g, "")
          );

          if (vehicle) {
            setVehicleInfo({
              entry_time: vehicle.entry_time || null,
              exit_time: vehicle.exit_time || null,
              fee: vehicle.fee || 0,
              duration: vehicle.duration || null,
              customer_type:
                vehicle.customer_type || vehicle.vehicle_type || null,
              is_subscriber: vehicle.is_subscriber || false,
            });
          } else {
            setVehicleInfo({
              entry_time: null,
              exit_time: null,
              fee: 0,
              duration: null,
              customer_type: null,
              is_subscriber: false,
            });
          }
        }
      } catch (err) {
        // Silent fail
      }
    };

    const timeoutId = setTimeout(fetchVehicleInfo, 500);
    return () => clearTimeout(timeoutId);
  }, [plateText]);

  // WebRTC connection logic
  useEffect(() => {
    let cancelled = false;

    const cleanupRetry = () => {
      if (retryRef.current) {
        clearTimeout(retryRef.current);
        retryRef.current = null;
      }
    };

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
  }, [
    camera?.id,
    camera?.status,
    streamProxy?.available,
    streamProxy?.default_mode,
    streamProxy?.supports_annotated,
    wantsAnnotated,
  ]);

  // WebSocket for detections and barrier status
  useEffect(() => {
    const cleanupWebSocket = () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };

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

    ws.onopen = () => {};

    ws.onmessage = (event) => {
      try {
        const data = event.data;
        if (data === "ping") {
          ws.send("pong");
          return;
        }
        if (data === "pong") return;

        const message = JSON.parse(data);

        // Handle barrier status updates
        if (message.type === "barrier_status") {
          const status = message.data || {};
          setBarrierStatus({
            is_open: status.is_open || false,
            enabled: status.enabled !== undefined ? status.enabled : true,
          });
          return;
        }

        if (message.type === "detections") {
          const detectionsData = message.data || [];
          lastDetectionsRef.current = detectionsData;
          setDetections(detectionsData);
          lastDetectionTimeRef.current = Date.now();

          // Find detection with OCR processing
          const detectionProcessing = detectionsData.find(
            (det) => det.ocr_status === "processing" && det.plate_image
          );

          // Find detection with finalized text
          const detectionWithText = detectionsData.find((det) => det.text);
          const normalizedPlate = detectionWithText?.text
            ?.trim()
            ?.toUpperCase();

          // Step 1: Show image while processing
          if (detectionProcessing && !normalizedPlate) {
            setPlateImage(detectionProcessing.plate_image);
            setNotificationMessage("🔍 Đang đọc biển số...");
            setCannotReadPlate(false);

            setTimeout(() => {
              if (notificationMessage === "🔍 Đang đọc biển số...") {
                setNotificationMessage(null);
              }
            }, 2000);
          }

          // Step 2: Process finalized text
          if (normalizedPlate) {
            const isValidFormat = validatePlateNumber(normalizedPlate);

            if (!isValidFormat) {
              // Invalid format - ignore silently
              return;
            }

            // Valid format - update UI
            setPlateValid(true);
            if (detectionWithText?.plate_image) {
              setPlateImage(detectionWithText.plate_image);
            }

            if (!userEditedRef.current && !showEditModal) {
              setPlateText(normalizedPlate);
              setPlateSource("auto");
              setPlateConfidence(detectionWithText?.confidence || 0);
            }
            setCannotReadPlate(false);

            if (notificationMessage === "🔍 Đang đọc biển số...") {
              setNotificationMessage(null);
            }
          } else {
            if (detectionsData.length > 0) {
              if (!plateTextRef.current) {
                setCannotReadPlate(true);
              }
            }
          }
        }
      } catch (err) {
        // Silent fail
      }
    };

    ws.onerror = () => {};

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
  }, [controlProxy?.ws_url, camera?.id, showEditModal, notificationMessage]);

  // Fetch barrier status on mount
  useEffect(() => {
    if (!controlProxy?.barrier_status_url) return;

    const fetchBarrierStatus = async () => {
      try {
        const response = await fetch(controlProxy.barrier_status_url);
        if (response.ok) {
          const result = await response.json();
          if (result.success) {
            setBarrierStatus({
              is_open: result.is_open || false,
              enabled: result.enabled || false,
            });
          }
        }
      } catch (err) {
        // Silent fail
      }
    };

    fetchBarrierStatus();
  }, [controlProxy?.barrier_status_url]);

  // Auto-open barrier when valid plate detected
  useEffect(() => {
    const shouldAutoOpen =
      !isOpening &&
      !showEditModal &&
      plateText.trim() &&
      controlProxy?.open_barrier_url &&
      !barrierStatus.is_open &&
      plateValid;

    if (shouldAutoOpen) {
      const timeoutId = setTimeout(() => {
        handleOpenBarrier();
      }, 500);

      return () => clearTimeout(timeoutId);
    }
  }, [
    isOpening,
    showEditModal,
    plateText,
    controlProxy?.open_barrier_url,
    barrierStatus.is_open,
    plateValid,
  ]);

  // Fullscreen handling
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
      setIsFullscreen((prev) => !prev);
    }
  };

  const closeBarrier = async () => {
    if (!controlProxy?.base_url && !controlProxy?.open_barrier_url) return;

    const baseUrl =
      controlProxy.base_url ||
      controlProxy.open_barrier_url.replace("/api/open-barrier", "");
    const closeBarrierUrl = `${baseUrl}/api/close-barrier`;

    try {
      const response = await fetch(closeBarrierUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      const result = await response.json();

      if (result.success) {
        setBarrierStatus({
          is_open: result.is_open !== undefined ? result.is_open : false,
          enabled: true,
        });

        setNotificationMessage("✅ Barrier đã đóng thành công!");
        setTimeout(() => {
          setNotificationMessage(null);
        }, 3000);

        // Reset all state
        setPlateText("");
        setPlateSource("");
        setPlateConfidence(0);
        setPlateImage(null);
        setDetections([]);
        lastDetectionsRef.current = [];
        setPlateValid(true);
        setCannotReadPlate(false);
        setUserEdited(false);
        userEditedRef.current = false;
        plateTextRef.current = "";
        setBarrierOpenedPlate(null);
      } else {
        setNotificationMessage(`❌ ${result.error || "Không thể đóng cửa"}`);
        setTimeout(() => {
          setNotificationMessage(null);
        }, 5000);
      }

      setBarrierOpenedPlate(null);
    } catch (err) {
      setNotificationMessage(`Lỗi kết nối: ${err.message}`);
      setTimeout(() => {
        setNotificationMessage(null);
      }, 5000);
    }
  };

  const handleOpenBarrier = async (
    plateOverride = null,
    confidenceOverride = null
  ) => {
    const normalizedPlate = (
      plateOverride || plateTextRef.current?.trim()
    )?.toUpperCase();

    if (!normalizedPlate) {
      setNotificationMessage("Vui lòng nhập biển số!");
      setTimeout(() => {
        setNotificationMessage(null);
      }, 3000);
      return;
    }

    if (!controlProxy?.open_barrier_url) {
      setNotificationMessage("Chưa cấu hình API mở barrier cho camera này.");
      setTimeout(() => {
        setNotificationMessage(null);
      }, 3000);
      return;
    }

    try {
      setIsOpening(true);
      const response = await fetch(controlProxy.open_barrier_url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plate_text: normalizedPlate,
          confidence:
            confidenceOverride !== null ? confidenceOverride : plateConfidence,
          source: plateSource || "manual",
        }),
      });

      const result = await response.json();

      if (result.success) {
        if (result.barrier_opened) {
          setBarrierStatus({
            is_open: true,
            enabled: true,
          });

          setNotificationMessage(
            `🚪 Barrier đã mở! Xe ${normalizedPlate} vui lòng vào.`
          );
        } else {
          setNotificationMessage(result.message || "✅ Đã xác nhận thành công");
        }

        const vehicleData = result.vehicle_info || result;
        if (
          vehicleData.entry_time ||
          vehicleData.exit_time ||
          vehicleData.fee !== undefined ||
          vehicleData.duration
        ) {
          setVehicleInfo({
            entry_time: vehicleData.entry_time || null,
            exit_time: vehicleData.exit_time || null,
            fee: vehicleData.fee !== undefined ? vehicleData.fee : 0,
            duration: vehicleData.duration || null,
            customer_type:
              vehicleData.customer_type || vehicleData.vehicle_type || null,
            is_subscriber: vehicleData.is_subscriber || false,
          });
        }

        setTimeout(() => {
          setNotificationMessage(null);
        }, 3000);

        setBarrierOpenedPlate(normalizedPlate);

        if (typeof onHistoryUpdate === "function") {
          onHistoryUpdate();
        }
      } else {
        setNotificationMessage(`❌ ${result.error || "Không thể mở cửa"}`);
        setTimeout(() => {
          setNotificationMessage(null);
        }, 5000);
      }
    } catch (err) {
      setNotificationMessage(`❌ Lỗi kết nối: ${err.message}`);
      setTimeout(() => {
        setNotificationMessage(null);
      }, 5000);
    } finally {
      setIsOpening(false);
    }
  };

  const handleConfirmEdit = (normalizedPlate) => {
    setPlateText(normalizedPlate);
    plateTextRef.current = normalizedPlate;
    setUserEdited(true);
    userEditedRef.current = true;
    setPlateSource("manual");
    setPlateValid(true);
    setShowEditModal(false);

    setNotificationMessage("✅ Đã cập nhật biển số!");
    setTimeout(() => {
      setNotificationMessage(null);
    }, 2000);
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
      <CameraHeader
        cameraInfo={cameraInfo}
        barrierStatus={barrierStatus}
        isConnected={isConnected}
        isFullscreen={isFullscreen}
      />

      <div
        className="card-body p-0"
        style={{ flex: "1 1 auto", minHeight: 0, overflow: "hidden" }}
      >
        <VideoStream
          videoRef={videoRef}
          canvasRef={canvasRef}
          isVideoLoaded={isVideoLoaded}
          detections={detections}
          lastDetectionTime={lastDetectionTimeRef.current}
          onFullscreenToggle={toggleFullscreen}
          isFullscreen={isFullscreen}
        />
      </div>

      <div
        className={`card-footer bg-light p-3 ${isFullscreen ? "d-none" : ""}`}
      >
        <h6 className="mb-3 text-primary">
          <i className="bi bi-info-circle-fill me-1"></i>
          Thông tin xe
        </h6>

        <PlateImage plateImage={plateImage} isFullscreen={isFullscreen} />

        <PlateInput
          plateText={plateText}
          plateSource={plateSource}
          onEditClick={() => setShowEditModal(true)}
          isFullscreen={isFullscreen}
        />

        <VehicleInfo
          vehicleInfo={vehicleInfo}
          cameraType={cameraInfo?.type}
          isFullscreen={isFullscreen}
        />

        {cannotReadPlate && (
          <div
            className="alert alert-warning mb-2 py-2 px-3"
            style={{ fontSize: "0.9rem" }}
          >
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            Không đọc được biển số, vui lòng nhập tay
          </div>
        )}

        <Notification message={notificationMessage} isFullscreen={isFullscreen} />

        <BarrierControls
          barrierStatus={barrierStatus}
          isOpening={isOpening}
          onCloseBarrier={closeBarrier}
          isFullscreen={isFullscreen}
        />
      </div>

      {error && (
        <div className="card-footer bg-danger text-white p-2 text-center">
          <small>
            <i className="bi bi-exclamation-triangle-fill me-1"></i>
            {error}
          </small>
        </div>
      )}

      <EditPlateModal
        show={showEditModal}
        initialPlateText={plateText}
        onClose={() => setShowEditModal(false)}
        onConfirm={handleConfirmEdit}
        onNotification={setNotificationMessage}
      />
    </div>
  );
};

export default CameraView;

