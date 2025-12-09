import { useEffect, useRef, useState } from "react";
import { CENTRAL_URL } from "../../config";
import { validatePlateNumber } from "../../utils/plateValidation";

//Import components
import CameraHeader from "./ui/CameraHeader";
import VideoStream from "./video/VideoStream";
import PlateImage from "./plate/PlateImage";
import PlateInput from "./plate/PlateInput";
import VehicleInfo from "./vehicle/VehicleInfo";
import Notification from "./ui/Notification";

const CameraView = ({ camera, onHistoryUpdate }) => {
  const streamProxy = camera?.stream_proxy;
  const controlProxy = camera?.control_proxy;

  const wantsAnnotated =
    streamProxy?.default_mode === "annotated" &&
    streamProxy?.supports_annotated !== false;

  //Refs
  const containerRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const peerRef = useRef(null);
  const wsRef = useRef(null);
  const retryRef = useRef(null);
  const userEditedRef = useRef(false);
  const plateTextRef = useRef("");
  const lastDetectionsRef = useRef([]);
  const [lastDetectionTime, setLastDetectionTime] = useState(0);

  //State
  const [isConnected, setIsConnected] = useState(false);
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [detections, setDetections] = useState([]);
  const [plateText, setPlateText] = useState("");
  const [plateSource, setPlateSource] = useState("");
  const [plateImage, setPlateImage] = useState(null);
  const [cannotReadPlate, setCannotReadPlate] = useState(false);
  const [cameraInfo, setCameraInfo] = useState({
    id: camera?.id,
    name: camera?.name,
    type: camera?.type,
    location: camera?.location,
    ip: camera?.ip || camera?.edge_ip || camera?.host,
  });
  const [userEdited, setUserEdited] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [notificationMessage, setNotificationMessage] = useState(null);
  const [vehicleInfo, setVehicleInfo] = useState({
    entry_time: null,
    exit_time: null,
    fee: 0,
    duration: null,
    customer_type: null,
    is_subscriber: false,
  });

  //Update camera info when camera changes
  useEffect(() => {
    setCameraInfo({
      id: camera?.id,
      name: camera?.name,
      type: camera?.type,
      location: camera?.location,
      ip: camera?.ip || camera?.edge_ip || camera?.host,
    });
  }, [
    camera?.id,
    camera?.name,
    camera?.type,
    camera?.location,
    camera?.ip,
    camera?.edge_ip,
    camera?.host,
  ]);

  //Sync refs with state
  useEffect(() => {
    userEditedRef.current = userEdited;
  }, [userEdited]);

  useEffect(() => {
    plateTextRef.current = plateText;
  }, [plateText]);

  //Fetch vehicle info when plate text changes
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
        //Silent fail
      }
    };

    const timeoutId = setTimeout(fetchVehicleInfo, 500);
    return () => clearTimeout(timeoutId);
  }, [plateText]);

  //WebRTC connection logic
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
        try {
          //Chi close neu chua closed
          if (peerRef.current.signalingState !== "closed") {
            peerRef.current.ontrack = null;
            peerRef.current.onconnectionstatechange = null;
            peerRef.current.close();
          }
        } catch (err) {
          console.warn("[CameraView] Error cleaning up peer:", err);
        } finally {
          peerRef.current = null;
        }
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
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.error || `HTTP ${response.status}: ${response.statusText}`
          );
        }

        const answer = await response.json();

        //Kiem tra xem answer co dung format khong
        if (!answer || !answer.sdp || !answer.type) {
          throw new Error(answer?.error || "Invalid answer format from server");
        }

        //Kiem tra signalingState truoc khi setRemoteDescription
        if (pc.signalingState === "closed") {
          throw new Error("PeerConnection is closed");
        }

        //Kiem tra lai mot lan nua sau khi await
        if (cancelled || pc.signalingState === "closed") {
          return;
        }

        await pc.setRemoteDescription(
          new RTCSessionDescription({
            sdp: answer.sdp,
            type: answer.type,
          })
        );
      } catch (err) {
        if (cancelled) return;
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

  //WebSocket for detections (auto-reconnect khi backend restart)
  useEffect(() => {
    let pingInterval = null;
    let reconnectTimer = null;

    const cleanupWebSocket = () => {
      if (wsRef.current) {
        try {
          wsRef.current.onclose = null;
          wsRef.current.close();
        } catch (e) {
          //ignore
        }
        wsRef.current = null;
      }
    };

    const connect = () => {
      //Neu khong co WS URL thi clear detections va khong ket noi
      if (!controlProxy?.ws_url) {
        lastDetectionsRef.current = [];
        setDetections([]);
        return;
      }

      //Dong ket noi cu truoc khi mo ket noi moi
      cleanupWebSocket();

      const ws = new WebSocket(controlProxy.ws_url);
      wsRef.current = ws;

      //Ping de giu ket noi song
      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            ws.send("ping");
          } catch {
            //ignore
          }
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

          if (message.type === "detections") {
            const detectionsData = message.data || [];
            lastDetectionsRef.current = detectionsData;
            setDetections(detectionsData);
            setLastDetectionTime(Date.now());

            //Find detection with OCR processing
            const detectionProcessing = detectionsData.find(
              (det) => det.ocr_status === "processing" && det.plate_image
            );

            //Find detection with finalized text
            const detectionWithText = detectionsData.find((det) => det.text);
            const normalizedPlate = detectionWithText?.text
              ?.trim()
              ?.toUpperCase();

            //Step 1: Show image while processing
            if (detectionProcessing && !normalizedPlate) {
              setPlateImage(detectionProcessing.plate_image);
              setNotificationMessage("Đang đọc biển số...");
              setCannotReadPlate(false);

              setTimeout(() => {
                setNotificationMessage((prev) => {
                  if (prev === "Đang đọc biển số...") {
                    return null;
                  }
                  return prev;
                });
              }, 2000);
            }

            //Step 2: Process finalized text
            if (normalizedPlate) {
              const isValidFormat = validatePlateNumber(normalizedPlate);

              if (!isValidFormat) {
                //Invalid format - ignore silently
                return;
              }

              //Check validation status tu backend
              const validationStatus = detectionWithText?.validation_status;
              const validationMessage = detectionWithText?.validation_message;
              const entrySaved = detectionWithText?.entry_saved;

              //Valid format - update UI
              if (detectionWithText?.plate_image) {
                setPlateImage(detectionWithText.plate_image);
              }

              if (!userEditedRef.current) {
                setPlateText(normalizedPlate);
                setPlateSource("auto");
              }
              setCannotReadPlate(false);

              //Hien thi thong bao ket qua
              if (entrySaved) {
                //Auto-saved thanh cong
                const entryResult = detectionWithText?.entry_result;
                setNotificationMessage(`Đã lưu: ${normalizedPlate} - ${entryResult?.message || "Thành công"}`);

                //Trigger history update
                if (onHistoryUpdate) {
                  setTimeout(() => onHistoryUpdate(), 500);
                }
              } else if (validationStatus === "invalid") {
                //Validation failed
                setNotificationMessage(`Lỗi: ${validationMessage || "Xe không hợp lệ"}`);
              } else {
                //Doc duoc bien so nhung khong auto-save (co the la cau hinh)
                setNotificationMessage((prev) => {
                  if (prev === "Đang đọc biển số...") {
                    return null;
                  }
                  return prev;
                });
              }

              //Clear notification sau 5s
              setTimeout(() => {
                setNotificationMessage((prev) => {
                  if (prev && (prev.includes("Đã lưu") || prev.includes("Lỗi"))) {
                    return null;
                  }
                  return prev;
                });
              }, 5000);
            } else {
              if (detectionsData.length > 0) {
                if (!plateTextRef.current) {
                  setCannotReadPlate(true);
                }
              }
            }
          }
        } catch (err) {
          //Silent fail
        }
      };

      ws.onerror = () => {};

      ws.onclose = () => {
        if (pingInterval) {
          clearInterval(pingInterval);
          pingInterval = null;
        }
        //Tu dong reconnect sau 3 giay neu day van la connection hien tai
        reconnectTimer = setTimeout(() => {
          if (wsRef.current === ws) {
            connect();
          }
        }, 3000);
      };
    };

    //Bat dau ket noi
    connect();

    return () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      if (pingInterval) {
        clearInterval(pingInterval);
      }
      cleanupWebSocket();
    };
  }, [controlProxy?.ws_url, camera?.id]);

  //Fullscreen handling
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

  const handlePlateConfirm = (normalizedPlate, message) => {
    if (!normalizedPlate) {
      //Validation failed, chi hien thi message
      setNotificationMessage(message);
      setTimeout(() => {
        setNotificationMessage(null);
      }, 3000);
      return;
    }

    //Validation thanh cong
    setPlateText(normalizedPlate);
    plateTextRef.current = normalizedPlate;
    setUserEdited(true);
    userEditedRef.current = true;
    setPlateSource("manual");

    if (message) {
      setNotificationMessage(message);
      setTimeout(() => {
        setNotificationMessage(null);
      }, 2000);
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
      <CameraHeader
        cameraInfo={cameraInfo}
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
          lastDetectionTime={lastDetectionTime}
          onFullscreenToggle={toggleFullscreen}
          isFullscreen={isFullscreen}
        />
      </div>

      <div
        className={`card-footer bg-light p-3 ${isFullscreen ? "d-none" : ""}`}
      >
        <PlateImage plateImage={plateImage} />

        <PlateInput
          plateText={plateText}
          plateSource={plateSource}
          onPlateConfirm={handlePlateConfirm}
        />

        <VehicleInfo vehicleInfo={vehicleInfo} cameraType={cameraInfo?.type} />

        {cannotReadPlate && (
          <div
            className="alert alert-warning mb-2 py-2 px-3"
            style={{ fontSize: "0.9rem" }}
          >
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            Không đọc được biển số, vui lòng nhập tay
          </div>
        )}

        <Notification message={notificationMessage} />
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
