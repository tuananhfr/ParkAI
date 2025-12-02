import { useState, useEffect } from "react";
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import { CENTRAL_URL } from "./config";
import CameraView from "./components/CameraView";
import HistoryPanel from "./components/HistoryPanel";
import SettingsModal from "./components/SettingsModal";

// ==================== Main App ====================
function App() {
  const [cameras, setCameras] = useState([]);
  const [historyKey, setHistoryKey] = useState(0);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showStaffDropdown, setShowStaffDropdown] = useState(false);
  const [staff, setStaff] = useState([]);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    // Fetch stats NGAY để có UI trong 100ms
    fetchStats();
    const statsInterval = setInterval(fetchStats, 10000);

    // ===== PROGRESSIVE CAMERA LOADING =====
    // Load cameras tuần tự với delay 300ms/camera để tránh quá tải WebRTC
    const loadCamerasProgressively = async () => {
      try {
        const response = await fetch(`${CENTRAL_URL}/api/cameras`);
        const data = await response.json();

        if (data.success && data.cameras) {
          // Sort cameras by ID để load theo thứ tự
          const sortedCameras = data.cameras.sort((a, b) => a.id - b.id);

          // Load từng camera với delay 300ms để tránh overload
          for (let i = 0; i < sortedCameras.length; i++) {
            // Delay 300ms giữa mỗi camera (ngoại trừ camera đầu tiên)
            if (i > 0) {
              await new Promise((resolve) => setTimeout(resolve, 300));
            }

            // Add camera vào state
            setCameras((prev) => {
              const exists = prev.find((c) => c.id === sortedCameras[i].id);
              if (exists) {
                // Update existing camera
                return prev.map((c) =>
                  c.id === sortedCameras[i].id ? sortedCameras[i] : c
                );
              } else {
                // Add new camera
                return [...prev, sortedCameras[i]];
              }
            });
          }

          console.log(
            `[Cameras] Loaded ${sortedCameras.length} cameras progressively`
          );
        }
      } catch (err) {
        console.error("[Cameras] Failed to load cameras:", err);
      }
    };

    // Start progressive loading NGAY
    loadCamerasProgressively();

    // WebSocket cho camera updates (CHẠY SONG SONG - real-time updates)
    const wsUrl = CENTRAL_URL.replace("http", "ws") + "/ws/cameras";
    let ws = null;
    let reconnectTimer = null;
    let pingInterval = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("[Cameras] WebSocket connected");

          // Start ping interval khi connection mở
          pingInterval = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              try {
                ws.send("ping");
              } catch (err) {
                console.error("[Cameras] Ping error:", err);
                if (pingInterval) clearInterval(pingInterval);
              }
            } else {
              if (pingInterval) clearInterval(pingInterval);
            }
          }, 10000); // Ping mỗi 10 giây
        };

        ws.onmessage = (event) => {
          try {
            const data = event.data;
            // Handle ping/pong
            if (data === "ping") {
              ws.send("pong");
              return;
            }
            if (data === "pong") {
              return;
            }

            const message = JSON.parse(data);
            if (message.type === "cameras_update" && message.data) {
              // UPDATE cameras qua WebSocket (realtime)
              setCameras(message.data.cameras || []);
            }
          } catch (err) {
            console.error("[Cameras] WebSocket message error:", err);
          }
        };

        ws.onerror = (error) => {
          console.error("[Cameras] WebSocket error:", error);
        };

        ws.onclose = () => {
          console.log("[Cameras] WebSocket disconnected, reconnecting...");
          // Cleanup ping interval
          if (pingInterval) {
            clearInterval(pingInterval);
            pingInterval = null;
          }
          // Reconnect sau 1 giây (giảm từ 3s)
          reconnectTimer = setTimeout(connect, 1000);
        };
      } catch (err) {
        console.error("[Cameras] WebSocket connection error:", err);
        reconnectTimer = setTimeout(connect, 1000);
      }
    };

    connect();

    return () => {
      if (statsInterval) clearInterval(statsInterval);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingInterval) clearInterval(pingInterval);
      if (ws) {
        ws.onclose = null; // Prevent reconnection
        ws.close();
      }
    };
  }, []);

  const fetchCameras = async () => {
    // Fallback: Fetch cameras nếu WebSocket không kết nối được
    try {
      const response = await fetch(`${CENTRAL_URL}/api/cameras`);
      const data = await response.json();
      if (data.success) {
        setCameras(data.cameras);
      }
    } catch (err) {
      console.error("[Cameras] Fetch error:", err);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(
        `${CENTRAL_URL}/api/parking/history?limit=1`
      );
      const data = await response.json();
      if (data.success && data.stats) {
        setStats(data.stats);
      }
    } catch (err) {}
  };

  const handleHistoryUpdate = () => {
    setHistoryKey((prev) => prev + 1);
  };

  const fetchStaff = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/staff`);
      const data = await response.json();
      if (data.success) {
        setStaff(data.staff || []);
      }
    } catch (err) {
      console.error("[Staff] Fetch error:", err);
    }
  };

  const toggleStaffStatus = (staffId) => {
    setStaff((prev) =>
      prev.map((person) =>
        person.id === staffId
          ? {
              ...person,
              status: person.status === "active" ? "inactive" : "active",
            }
          : person
      )
    );
  };

  const saveStaffChanges = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/staff`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ staff }),
      });
      const data = await response.json();
      if (data.success) {
        setShowStaffDropdown(false);
        // Refresh staff list
        fetchStaff();
      } else {
        alert(`Lỗi: ${data.error || "Không thể lưu thay đổi"}`);
      }
    } catch (err) {
      alert("Không thể kết nối đến server");
    }
  };

  return (
    <div
      className="d-flex flex-column"
      style={{ width: "100vw", height: "100vh", overflow: "hidden" }}
    >
      <div className="bg-primary text-white py-1 px-2 d-flex justify-content-between align-items-center">
        {stats && (
          <div className="row g-1 text-center flex-grow-1 me-2">
            <div className="col">
              <div
                className="fw-bold text-white"
                style={{
                  fontSize: "1rem",
                  lineHeight: "1.2",
                }}
              >
                {stats.entries_today || 0}
              </div>
              <div
                className="text-white-50"
                style={{ fontSize: "0.7rem", lineHeight: "1" }}
              >
                VÀO
              </div>
            </div>
            <div className="col position-relative">
              <div
                className="position-absolute start-0 top-0 bottom-0"
                style={{
                  width: "1px",
                  backgroundColor: "rgba(255, 255, 255, 0.25)",
                }}
              ></div>
              <div
                className="fw-bold text-white"
                style={{
                  fontSize: "1rem",
                  lineHeight: "1.2",
                }}
              >
                {stats.exits_today || 0}
              </div>
              <div
                className="text-white-50"
                style={{ fontSize: "0.7rem", lineHeight: "1" }}
              >
                RA
              </div>
            </div>
            <div className="col position-relative">
              <div
                className="position-absolute start-0 top-0 bottom-0"
                style={{
                  width: "1px",
                  backgroundColor: "rgba(255, 255, 255, 0.25)",
                }}
              ></div>
              <div
                className="fw-bold text-white"
                style={{
                  fontSize: "1rem",
                  lineHeight: "1.2",
                }}
              >
                {stats.vehicles_in_parking || 0}
              </div>
              <div
                className="text-white-50"
                style={{ fontSize: "0.7rem", lineHeight: "1" }}
              >
                Trong bãi
              </div>
            </div>
            <div className="col position-relative">
              <div
                className="position-absolute start-0 top-0 bottom-0"
                style={{
                  width: "1px",
                  backgroundColor: "rgba(255, 255, 255, 0.25)",
                }}
              ></div>
              <div
                className="fw-bold text-white"
                style={{
                  fontSize: "1rem",
                  lineHeight: "1.2",
                }}
              >
                {((stats.revenue_today || 0) / 1000).toFixed(0)}K
              </div>
              <div
                className="text-white-50"
                style={{ fontSize: "0.7rem", lineHeight: "1" }}
              >
                Thu
              </div>
            </div>
          </div>
        )}
        <div className="d-flex gap-2">
          <button
            className="btn btn-light btn-sm"
            onClick={() => setShowHistoryModal(true)}
            style={{
              padding: "0.25rem 0.5rem",
              fontSize: "0.75rem",
            }}
          >
            <i className="bi bi-clock-history me-1"></i>
            Xem lịch sử
          </button>

          {/* Staff Dropdown */}
          <div className="position-relative">
            <button
              className="btn btn-light btn-sm"
              onClick={() => {
                setShowStaffDropdown(!showStaffDropdown);
                if (!showStaffDropdown) {
                  fetchStaff();
                }
              }}
              style={{
                padding: "0.25rem 0.5rem",
                fontSize: "0.75rem",
              }}
            >
              <i className="bi bi-people-fill me-1"></i>
              Người trực
            </button>
            {showStaffDropdown && (
              <>
                <div
                  className="position-fixed"
                  style={{
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    zIndex: 999,
                  }}
                  onClick={() => setShowStaffDropdown(false)}
                ></div>
                <div
                  className="position-absolute end-0 mt-1 bg-white border rounded shadow-lg"
                  style={{
                    minWidth: "320px",
                    maxHeight: "450px",
                    overflowY: "auto",
                    zIndex: 1000,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="p-2 border-bottom bg-light">
                    <div className="d-flex justify-content-between align-items-center">
                      <strong>
                        <i className="bi bi-people me-2"></i>
                        Danh sách người trực
                      </strong>
                      <button
                        className="btn-close btn-close-sm"
                        onClick={() => setShowStaffDropdown(false)}
                      ></button>
                    </div>
                  </div>
                  <div
                    className="p-2"
                    style={{ maxHeight: "350px", overflowY: "auto" }}
                  >
                    {staff.length === 0 ? (
                      <div className="text-muted text-center py-3">
                        <small>Chưa có dữ liệu người trực</small>
                      </div>
                    ) : (
                      staff.map((person) => (
                        <div
                          key={person.id}
                          className="form-check py-2 border-bottom"
                        >
                          <input
                            className="form-check-input"
                            type="checkbox"
                            checked={person.status === "active"}
                            onChange={() => toggleStaffStatus(person.id)}
                            id={`staff-${person.id}`}
                          />
                          <label
                            className="form-check-label d-flex justify-content-between align-items-center w-100"
                            htmlFor={`staff-${person.id}`}
                            style={{ cursor: "pointer" }}
                          >
                            <div className="flex-grow-1">
                              <div className="fw-bold">{person.name}</div>
                              <small className="text-muted">
                                {person.position || "Bảo vệ"} •{" "}
                                {person.shift || ""}
                              </small>
                            </div>
                            <span
                              className={`badge ms-2 ${
                                person.status === "active"
                                  ? "bg-success"
                                  : "bg-secondary"
                              }`}
                            >
                              {person.status === "active"
                                ? "Hoạt động"
                                : "Nghỉ"}
                            </span>
                          </label>
                        </div>
                      ))
                    )}
                  </div>
                  <div className="p-2 border-top bg-light">
                    <button
                      className="btn btn-primary btn-sm w-100"
                      onClick={saveStaffChanges}
                    >
                      <i className="bi bi-save me-1"></i>
                      Lưu thay đổi
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>

          <button
            className="btn btn-light btn-sm"
            onClick={() => setShowSettingsModal(true)}
            style={{
              padding: "0.25rem 0.5rem",
              fontSize: "0.75rem",
            }}
          >
            <i className="bi bi-gear-fill me-1"></i>
            Cài đặt
          </button>
        </div>
      </div>

      <div className="flex-grow-1 p-2 overflow-hidden">
        <div className="row g-2 h-100">
          {cameras.length === 0 ? (
            <div className="col-12 h-100 d-flex flex-column align-items-center justify-content-center text-muted">
              <i className="bi bi-camera-video-off fs-1 mb-2"></i>
              <div>Chưa có camera nào kết nối</div>
            </div>
          ) : (
            cameras.map((camera) => (
              <div key={camera.id} className="col-12 col-md-6 col-lg-3 h-100">
                <CameraView
                  camera={camera}
                  onHistoryUpdate={handleHistoryUpdate}
                />
              </div>
            ))
          )}
        </div>
      </div>

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
                <HistoryPanel key={historyKey} backendUrl={CENTRAL_URL} />
              </div>
            </div>
          </div>
        </div>
      )}

      <SettingsModal
        show={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        onSaveSuccess={fetchCameras}
      />
    </div>
  );
}

export default App;
