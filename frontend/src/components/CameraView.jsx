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
  const [plateImage, setPlateImage] = useState(null); // Ảnh biển số cắt từ detection
  const [cannotReadPlate, setCannotReadPlate] = useState(false);
  const [plateValid, setPlateValid] = useState(true); // Biển số có hợp lệ không
  const [isOpening, setIsOpening] = useState(false);
  const [cameraInfo, setCameraInfo] = useState({
    name: camera?.name,
    type: camera?.type,
    location: camera?.location,
  });
  const [userEdited, setUserEdited] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
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
  });

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

  // Fetch vehicle info từ history khi có biển số
  useEffect(() => {
    const fetchVehicleInfo = async () => {
      if (!plateText || plateText.trim().length < 5) {
        // Reset vehicle info nếu không có biển số hợp lệ
        setVehicleInfo({
          entry_time: null,
          exit_time: null,
          fee: 0,
          duration: null,
          customer_type: null,
        });
        return;
      }

      try {
        // Tìm trong history theo plate_id hoặc plate_view
        const response = await fetch(
          `${CENTRAL_URL}/api/parking/history?limit=100&today_only=false`
        );
        const data = await response.json();

        if (data.success && data.history) {
          // Tìm vehicle gần nhất với biển số này
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
            });
          } else {
            // Không tìm thấy, giữ nguyên hoặc reset
            setVehicleInfo({
              entry_time: null,
              exit_time: null,
              fee: 0,
              duration: null,
              customer_type: null,
            });
          }
        }
      } catch (err) {
        // Lỗi thì không làm gì, giữ nguyên vehicleInfo hiện tại
      }
    };

    // Debounce để tránh fetch quá nhiều
    const timeoutId = setTimeout(fetchVehicleInfo, 500);
    return () => clearTimeout(timeoutId);
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

        // Handle barrier status updates (PUSH từ backend, không polling!)
        if (message.type === "barrier_status") {
          const status = message.data || {};
          setBarrierStatus({
            is_open: status.is_open || false,
            enabled: status.enabled !== undefined ? status.enabled : true, // Default enabled = true
          });
          return;
        }

        if (message.type === "detections") {
          const detectionsData = message.data || [];
          lastDetectionsRef.current = detectionsData;
          setDetections(detectionsData);
          lastDetectionTimeRef.current = Date.now();

          // ========== FLOW MỚI: XỬ LÝ 2 BƯỚC (ẢNH TRƯỚC, TEXT SAU) ==========

          // Tìm detection có OCR đang xử lý (có ảnh, chưa có text)
          const detectionProcessing = detectionsData.find(
            (det) => det.ocr_status === "processing" && det.plate_image
          );

          // Tìm detection đã OCR xong (có text + finalized)
          const detectionWithFinalized = detectionsData.find(
            (det) => det.text && det.finalized === true
          );
          const detectionWithText = detectionsData.find((det) => det.text);

          const normalizedPlate = detectionWithText?.text
            ?.trim()
            ?.toUpperCase();
          const finalizedPlate = detectionWithFinalized?.text
            ?.trim()
            ?.toUpperCase();

          // BƯỚC 1: Nhận ảnh (chưa có text) - Hiển thị "Đang đọc biển số..."
          if (detectionProcessing && !normalizedPlate) {
            setPlateImage(detectionProcessing.plate_image);
            setNotificationMessage("🔍 Đang đọc biển số...");
            setCannotReadPlate(false);

            // Clear notification sau 2s nếu không có update
            setTimeout(() => {
              if (notificationMessage === "🔍 Đang đọc biển số...") {
                setNotificationMessage(null);
              }
            }, 2000);
          }

          // BƯỚC 2: Nhận text sau khi OCR xong
          if (normalizedPlate) {
            // BƯỚC 3: CHECK VALIDATION STATUS
            const validationStatus = detectionWithText?.validation_status;
            const validationMessage =
              detectionWithText?.validation_message || "";

            if (validationStatus === "invalid") {
              // Biển số không hợp lệ → Cảnh báo và reset
              setPlateValid(false);
              setNotificationMessage(`⚠️ ${validationMessage}`);
              setTimeout(() => {
                setNotificationMessage(null);
              }, 5000);

              // Reset img và text
              if (!userEditedRef.current) {
                setPlateText("");
                setPlateSource("");
                setPlateConfidence(0);
                setPlateImage(null);
              }
              setCannotReadPlate(true);
            } else {
              // Biển số hợp lệ → Hiển thị bình thường
              setPlateValid(true);
              // Cập nhật ảnh biển số cắt từ detection (nếu có)
              if (detectionWithText?.plate_image) {
                setPlateImage(detectionWithText.plate_image);
              }

              if (!userEditedRef.current) {
                setPlateText(normalizedPlate);
                setPlateSource("auto");
                setPlateConfidence(detectionWithText?.confidence || 0);
              }
              setCannotReadPlate(false);

              // Clear "Đang đọc biển số..." notification
              if (notificationMessage === "🔍 Đang đọc biển số...") {
                setNotificationMessage(null);
              }
            }
          } else {
            // Không detect được plate
            if (detectionsData.length > 0) {
              if (!plateTextRef.current) {
                setCannotReadPlate(true);
              }
            }
          }
        }
      } catch (err) {}
    };

    ws.onerror = (err) => {};

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
      // ========== XE RA KHỎI TẦM CAM (detection timeout > 1s) ==========
      // KHÔNG RESET TEXT - Giữ lại text đã OCR để user có thể mở/đóng cửa
      // Chỉ clear detections để không vẽ boxes nữa

      lastDetectionsRef.current = [];
      setDetections([]);
      setCannotReadPlate(false);

      // KHÔNG reset plateText, plateSource, plateConfidence, plateImage
      // Giữ lại để user có thể mở/đóng cửa ngay cả khi xe đã đi qua

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

  // Bỏ countdown - user sẽ click button đóng cửa thủ công

  const closeBarrier = async () => {
    if (!controlProxy?.base_url && !controlProxy?.open_barrier_url) return;

    // Sử dụng base_url nếu có, nếu không thì parse từ open_barrier_url
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
        // Cập nhật barrier status NGAY từ API response (optimistic update)
        // Luôn set is_open = false khi đóng cửa thành công
        setBarrierStatus({
          is_open: result.is_open !== undefined ? result.is_open : false,
          enabled: true, // Luôn set enabled = true
        });

        setNotificationMessage("✅ Barrier đã đóng thành công!");
        setTimeout(() => {
          setNotificationMessage(null);
        }, 3000);

        // ========== RESET TẤT CẢ SAU KHI ĐÓNG BARRIER VÀ LƯU DB ==========
        setPlateText("");
        setPlateSource("");
        setPlateConfidence(0);
        setPlateImage(null); // Xóa ảnh biển số
        setDetections([]); // Xóa box detection
        lastDetectionsRef.current = []; // Xóa detection cache
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

      // Reset state
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
        // Kiểm tra barrier status từ response
        if (result.barrier_opened) {
          // Cập nhật barrier status NGAY từ API response (optimistic update)
          // Không cần chờ WebSocket message
          setBarrierStatus({
            is_open: true,
            enabled: true, // Luôn set enabled = true khi mở thành công
          });

          setNotificationMessage(
            `🚪 Barrier đã mở! Xe ${normalizedPlate} vui lòng vào.`
          );
        } else {
          setNotificationMessage(result.message || "✅ Đã xác nhận thành công");
        }

        // Lưu thông tin vehicle từ response
        if (
          result.entry_time ||
          result.exit_time ||
          result.fee ||
          result.duration
        ) {
          setVehicleInfo({
            entry_time: result.entry_time || null,
            exit_time: result.exit_time || null,
            fee: result.fee || 0,
            duration: result.duration || null,
            customer_type: result.customer_type || result.vehicle_type || null,
          });
        }

        setTimeout(() => {
          setNotificationMessage(null);
        }, 3000);

        // Lưu biển số đã mở cửa để track
        setBarrierOpenedPlate(normalizedPlate);

        // Không reset plate text - giữ lại để user có thể đóng cửa

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

  // Fetch barrier status ONCE on mount (để có initial state)
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
      } catch (err) {}
    };

    // CHỈ fetch 1 LẦN khi mount - không polling!
    fetchBarrierStatus();

    // KHÔNG CÒN setInterval - updates qua WebSocket!
  }, [controlProxy?.barrier_status_url]);

  // ========== TỰ ĐỘNG MỞ BARRIER KHI CÓ BIỂN SỐ HỢP LỆ ==========
  useEffect(() => {
    // Kiểm tra tất cả điều kiện giống button "Mở barrier"
    const shouldAutoOpen =
      !isOpening &&
      plateText.trim() &&
      controlProxy?.open_barrier_url &&
      !barrierStatus.is_open &&
      plateValid;

    if (shouldAutoOpen) {
      // Debounce 500ms để tránh call API liên tục khi OCR đang cập nhật
      const timeoutId = setTimeout(() => {
        handleOpenBarrier();
      }, 500);

      return () => clearTimeout(timeoutId);
    }
  }, [
    isOpening,
    plateText,
    controlProxy?.open_barrier_url,
    barrierStatus.is_open,
    plateValid,
  ]);

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
            <select
              className={`form-select form-select-sm ${
                cameraInfo.type === "ENTRY"
                  ? "bg-success text-white border-success"
                  : "bg-danger text-white border-danger"
              }`}
              style={{
                width: "auto",
                minWidth: "80px",
                fontWeight: "600",
                cursor: "pointer",
                fontSize: "0.875rem",
                padding: "0.25rem 1.75rem 0.25rem 0.5rem",
                borderRadius: "0.375rem",
                border: "2px solid",
                transition: "all 0.2s ease",
                boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
              }}
              value={cameraInfo.type}
              onChange={async (e) => {
                const newType = e.target.value;
                try {
                  const response = await fetch(
                    `${controlProxy?.base_url || ""}/api/camera/type`,
                    {
                      method: "PUT",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ type: newType }),
                    }
                  );

                  if (response.ok) {
                    const data = await response.json();
                    setCameraInfo((prev) => ({
                      ...prev,
                      type: data.camera.type,
                    }));
                  } else {
                    e.target.value = cameraInfo.type; // Revert
                  }
                } catch (error) {
                  e.target.value = cameraInfo.type; // Revert
                }
              }}
              onMouseEnter={(e) => {
                e.target.style.transform = "scale(1.05)";
                e.target.style.boxShadow = "0 4px 8px rgba(0,0,0,0.2)";
              }}
              onMouseLeave={(e) => {
                e.target.style.transform = "scale(1)";
                e.target.style.boxShadow = "0 2px 4px rgba(0,0,0,0.1)";
              }}
            >
              <option value="ENTRY" className="bg-white text-dark">
                VÀO
              </option>
              <option value="EXIT" className="bg-white text-dark">
                RA
              </option>
            </select>
          )}

          <span
            className={`badge ${
              barrierStatus.is_open ? "bg-warning" : "bg-secondary"
            }`}
            title={
              barrierStatus.is_open ? "Barrier đang mở" : "Barrier đang đóng"
            }
          >
            <i
              className={`bi ${
                barrierStatus.is_open
                  ? "bi-door-open-fill"
                  : "bi-door-closed-fill"
              } me-1`}
            ></i>
            {barrierStatus.is_open ? "MỞ" : "ĐÓNG"}
          </span>

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

        {/* Ảnh biển số - LUÔN HIỂN THỊ (empty hoặc có ảnh) */}
        <div className="mb-2 text-center">
          <label className="form-label small mb-1 text-secondary d-block">
            <i className="bi bi-image-fill me-1"></i>
            Ảnh biển số đã phát hiện
          </label>
          <div
            className="d-inline-block p-1 bg-white border border-2 rounded"
            style={{
              maxWidth: "100%",
              minHeight: "60px",
              minWidth: "150px",
              borderColor: plateImage ? "#0d6efd" : "#dee2e6",
              transition: "border-color 0.3s ease",
            }}
          >
            {plateImage ? (
              <img
                src={plateImage}
                alt="Cropped plate"
                style={{
                  maxWidth: "100%",
                  height: "auto",
                  maxHeight: "80px",
                  display: "block",
                  imageRendering: "crisp-edges",
                }}
              />
            ) : (
              <div
                className="d-flex align-items-center justify-content-center text-muted"
                style={{ minHeight: "60px" }}
              >
                <div className="text-center">
                  <i className="bi bi-image fs-4 opacity-25"></i>
                  <div className="small mt-1" style={{ fontSize: "0.7rem" }}>
                    Chờ phát hiện...
                  </div>
                </div>
              </div>
            )}
          </div>
          {plateImage && (
            <small
              className="text-muted d-block mt-0"
              style={{ fontSize: "0.65rem" }}
            >
              Vùng ảnh được OCR phân tích
            </small>
          )}
        </div>

        <div className="mb-2">
          <label className="form-label small mb-1 text-secondary">
            Biển số xe
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
                // Reset validation khi user edit (sẽ validate lại khi mở barrier)
                setPlateValid(true);
              }}
              className="form-control text-center fw-bold text-uppercase"
              placeholder="Chờ quét hoặc nhập tay..."
              style={{
                fontSize: "0.875rem",
                letterSpacing: "1px",
                padding: "0.25rem 0.5rem",
              }}
            />
            {plateSource === "auto" && (
              <span
                className="input-group-text bg-info text-white px-2"
                style={{ fontSize: "0.75rem" }}
              >
                <i className="bi bi-robot"></i>
              </span>
            )}
            {plateSource === "manual" && (
              <span
                className="input-group-text bg-warning text-dark px-2"
                style={{ fontSize: "0.75rem" }}
              >
                <i className="bi bi-pencil-fill"></i>
              </span>
            )}
          </div>
        </div>

        {/* Thông tin chi tiết - Tối ưu không gian */}
        <div className="mb-2">
          {/* Hàng 1: Vào + Loại khách */}
          <div className="d-flex justify-content-between align-items-center mb-1">
            <div className="text-muted" style={{ fontSize: "0.75rem" }}>
              {vehicleInfo.entry_time ? (
                <>
                  <i
                    className="bi bi-arrow-down-circle text-success me-1"
                    style={{ fontSize: "0.7rem" }}
                  ></i>
                  Vào: {vehicleInfo.entry_time}
                </>
              ) : (
                <>
                  <i
                    className="bi bi-arrow-down-circle me-1"
                    style={{ fontSize: "0.7rem", opacity: 0.5 }}
                  ></i>
                  Vào: Chưa có
                </>
              )}
            </div>
            <div className="d-flex align-items-center gap-1">
              <span className="text-muted" style={{ fontSize: "0.7rem" }}>
                <i className="bi bi-person-fill me-1"></i>Loại:
              </span>
              {vehicleInfo.customer_type ? (
                <span className="badge bg-info" style={{ fontSize: "0.7rem" }}>
                  {vehicleInfo.customer_type}
                </span>
              ) : (
                <span
                  className="badge bg-secondary"
                  style={{ fontSize: "0.7rem", opacity: 0.5 }}
                >
                  Khách lẻ
                </span>
              )}
            </div>
          </div>

          {/* Hàng 2: Ra + Giá vé (chỉ ở cổng EXIT) */}
          {cameraInfo?.type === "EXIT" && (
            <div className="d-flex justify-content-between align-items-center">
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                {vehicleInfo.exit_time ? (
                  <>
                    <i
                      className="bi bi-arrow-up-circle text-danger me-1"
                      style={{ fontSize: "0.7rem" }}
                    ></i>
                    Ra: {vehicleInfo.exit_time}
                  </>
                ) : (
                  <>
                    <i
                      className="bi bi-arrow-up-circle me-1"
                      style={{ fontSize: "0.7rem", opacity: 0.5 }}
                    ></i>
                    Ra: Chưa có
                  </>
                )}
              </div>
              <div className="text-end">
                <div
                  className={
                    vehicleInfo.fee > 0 ? "fw-bold text-success" : "text-muted"
                  }
                  style={{ fontSize: "0.85rem" }}
                >
                  {(vehicleInfo.fee || 0).toLocaleString("vi-VN")}
                  <strong>đ</strong>
                </div>
                {vehicleInfo.duration && (
                  <div className="text-muted" style={{ fontSize: "0.65rem" }}>
                    <i className="bi bi-clock me-1"></i>
                    {vehicleInfo.duration}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Thông báo không đọc được biển số */}
        {cannotReadPlate && (
          <div
            className="alert alert-warning mb-2 py-2 px-3"
            style={{ fontSize: "0.9rem" }}
          >
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            Không đọc được biển số, vui lòng nhập tay
          </div>
        )}

        {/* Thông báo */}
        {notificationMessage && (
          <div
            className={`alert ${
              notificationMessage?.includes("✅") ||
              notificationMessage?.includes("thành công") ||
              notificationMessage?.includes("🚪 Cửa đã mở")
                ? "alert-success"
                : notificationMessage?.includes("❌") ||
                  notificationMessage?.includes("Lỗi") ||
                  notificationMessage?.includes("Không thể")
                ? "alert-danger"
                : notificationMessage?.includes("🔒") ||
                  notificationMessage?.includes("Đang đóng")
                ? "alert-info"
                : "alert-info"
            } mb-2 py-2 px-3`}
            style={{ fontSize: "0.9rem" }}
          >
            <div className="d-flex align-items-center">
              <i
                className={`bi me-2 ${
                  notificationMessage?.includes("✅") ||
                  notificationMessage?.includes("thành công") ||
                  notificationMessage?.includes("🚪 Cửa đã mở")
                    ? "bi-check-circle-fill"
                    : notificationMessage?.includes("❌") ||
                      notificationMessage?.includes("Lỗi") ||
                      notificationMessage?.includes("Không thể")
                    ? "bi-exclamation-triangle-fill"
                    : notificationMessage?.includes("🔒") ||
                      notificationMessage?.includes("Đang đóng")
                    ? "bi-lock-fill"
                    : "bi-info-circle-fill"
                }`}
              ></i>
              <span>{notificationMessage}</span>
            </div>
          </div>
        )}

        {/* 2 BUTTON MỞ/ĐÓNG BARRIER - LUÔN HIỂN THỊ CẢ 2 */}
        <div className="d-flex gap-2 mt-2">
          {/* Button MỞ CỬA */}
          <button
            className={`btn flex-fill ${
              cameraInfo?.type === "ENTRY" ? "btn-success" : "btn-danger"
            }`}
            onClick={(e) => {
              if (
                !isOpening &&
                plateText.trim() &&
                controlProxy?.open_barrier_url &&
                !barrierStatus.is_open &&
                plateValid
              ) {
                handleOpenBarrier();
              }
            }}
            disabled={
              isOpening ||
              !plateText.trim() ||
              !controlProxy?.open_barrier_url ||
              barrierStatus.is_open || // Disable khi barrier đang mở
              !plateValid // Disable khi biển số không hợp lệ
            }
            style={{ fontSize: "1rem", padding: "10px" }}
          >
            {isOpening ? (
              <>
                <span className="spinner-border spinner-border-sm me-2"></span>
                Đang mở barrier...
              </>
            ) : (
              <>
                <i className="bi bi-door-open-fill me-2"></i>
                Mở barrier {cameraInfo?.type === "ENTRY" ? "VÀO" : "RA"}
              </>
            )}
          </button>

          {/* Button ĐÓNG BARRIER */}
          <button
            className="btn btn-danger flex-fill"
            onClick={closeBarrier}
            disabled={
              isOpening || !barrierStatus.is_open // Disable khi barrier đang đóng
            }
            style={{ fontSize: "1rem", padding: "10px" }}
          >
            <i className="bi bi-door-closed-fill me-2"></i>
            Đóng barrier
          </button>
        </div>
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
