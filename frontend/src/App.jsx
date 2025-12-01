import { useState, useEffect } from "react";
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import { CENTRAL_URL } from "./config";
import CameraView from "./components/CameraView";

// ==================== History Panel (dùng lại logic cũ) ====================
const HistoryPanel = ({ backendUrl }) => {
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState("all"); // all | today | in | out | in_parking
  const [searchText, setSearchText] = useState(""); // Tìm kiếm biển số

  const fetchHistory = async (isLoadMore = false) => {
    try {
      if (isLoadMore) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        setOffset(0);
        setHasMore(true);
      }

      const currentOffset = isLoadMore ? offset : 0;
      const params = new URLSearchParams();
      params.append("limit", "50");
      params.append("offset", currentOffset.toString());

      if (filter === "today") {
        params.append("today_only", "true");
      } else if (filter === "in") {
        params.append("status", "IN");
      } else if (filter === "in_parking") {
        params.append("status", "IN");
      } else if (filter === "out") {
        params.append("status", "OUT");
      }

      // Thêm search parameter nếu có
      if (searchText.trim()) {
        params.append("search", searchText.trim());
      }

      const response = await fetch(
        `${backendUrl}/api/parking/history?${params}`
      );
      const data = await response.json();

      if (data.success) {
        if (isLoadMore) {
          // Append new data
          setHistory((prev) => [...prev, ...data.history]);
          setOffset(currentOffset + data.history.length);
        } else {
          // Replace data
          setHistory(data.history);
          setOffset(data.history.length);
        }
        setStats(data.stats);

        // Check if there are more records
        setHasMore(data.history.length === 50);
      }
    } catch (err) {
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    // Load lần đầu hoặc khi filter/search thay đổi
    const timeoutId = setTimeout(() => {
      fetchHistory();
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [filter, searchText]);

  // WebSocket for real-time updates
  useEffect(() => {
    const wsUrl = backendUrl.replace('http', 'ws') + '/ws/history';
    let ws = null;
    let reconnectTimer = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('[History] WebSocket connected');
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            if (message.type === 'history_update') {
              // Fetch latest entry from database
              fetchHistory();
            }
          } catch (err) {
            console.error('[History] WebSocket message error:', err);
          }
        };

        ws.onclose = () => {
          console.log('[History] WebSocket disconnected, reconnecting...');
          reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = (err) => {
          console.error('[History] WebSocket error:', err);
        };
      } catch (err) {
        console.error('[History] WebSocket connection error:', err);
      }
    };

    connect();

    return () => {
      if (ws) {
        ws.close();
      }
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
    };
  }, [backendUrl]);

  return (
    <div className="card shadow-sm h-100">
      {/* Filter */}
      <div className="px-2 pt-2">
        <div className="btn-group btn-group-sm w-100" role="group">
          <button
            className={`btn ${
              filter === "all" ? "btn-primary" : "btn-outline-primary"
            }`}
            onClick={() => setFilter("all")}
          >
            Tất cả
          </button>
          <button
            className={`btn ${
              filter === "today" ? "btn-primary" : "btn-outline-primary"
            }`}
            onClick={() => setFilter("today")}
          >
            Hôm nay
          </button>
          <button
            className={`btn ${
              filter === "in_parking" ? "btn-info" : "btn-outline-info"
            }`}
            onClick={() => setFilter("in_parking")}
          >
            <i className="bi bi-car-front-fill me-1"></i>
            Trong bãi
          </button>
          <button
            className={`btn ${
              filter === "in" ? "btn-success" : "btn-outline-success"
            }`}
            onClick={() => setFilter("in")}
          >
            VÀO
          </button>
          <button
            className={`btn ${
              filter === "out" ? "btn-danger" : "btn-outline-danger"
            }`}
            onClick={() => setFilter("out")}
          >
            RA
          </button>
        </div>

        {/* Tìm kiếm biển số */}
        <div className="mt-2">
          <div className="input-group input-group-sm">
            <span className="input-group-text">
              <i className="bi bi-search"></i>
            </span>
            <input
              type="text"
              className="form-control"
              placeholder="Tìm kiếm biển số..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
            {searchText && (
              <button
                className="btn btn-outline-secondary"
                type="button"
                onClick={() => setSearchText("")}
              >
                <i className="bi bi-x"></i>
              </button>
            )}
          </div>
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
            <div>
              {searchText ? "Không tìm thấy kết quả" : "Chưa có dữ liệu"}
            </div>
          </div>
        ) : (
          <>
            <div className="list-group list-group-flush">
              {history.map((entry) => (
                <div key={entry.id} className="list-group-item p-2 border-bottom">
                  <div className="row g-1">
                    {/* Thông tin chính */}
                    <div className="col flex-grow-1">
                      {/* Biển số */}
                      <div className="mb-2">
                        <div
                          className="fw-bold text-primary"
                          style={{ fontSize: "1rem" }}
                        >
                          <i className="bi bi-123 me-1"></i>
                          {entry.plate_view || entry.plate_id}
                        </div>
                      </div>

                      {/* Giờ vào/ra */}
                      <div className="mb-1">
                        <div
                          className="text-muted mb-1"
                          style={{ fontSize: "0.7rem" }}
                        >
                          <i
                            className="bi bi-arrow-down-circle text-success me-1"
                            style={{ fontSize: "0.65rem" }}
                          ></i>
                          Vào: {entry.entry_time || "N/A"}
                          {entry.entry_camera_name && (
                            <span className="ms-1">
                              ({entry.entry_camera_name})
                            </span>
                          )}
                        </div>
                        {entry.exit_time ? (
                          <div
                            className="text-muted"
                            style={{ fontSize: "0.7rem" }}
                          >
                            <i
                              className="bi bi-arrow-up-circle text-danger me-1"
                              style={{ fontSize: "0.65rem" }}
                            ></i>
                            Ra: {entry.exit_time}
                            {entry.exit_camera_name && (
                              <span className="ms-1">
                                ({entry.exit_camera_name})
                              </span>
                            )}
                          </div>
                        ) : entry.status === "IN" ? (
                          <div
                            className="text-muted"
                            style={{ fontSize: "0.7rem" }}
                          >
                            <i
                              className="bi bi-clock text-info me-1"
                              style={{ fontSize: "0.65rem" }}
                            ></i>
                            Ra: Đang trong bãi
                          </div>
                        ) : null}
                      </div>

                      {/* Loại khách */}
                      <div className="mb-1">
                        <span className="badge bg-info">
                          <i className="bi bi-person-fill me-1"></i>
                          {entry.customer_type ||
                            entry.vehicle_type ||
                            "Khách lẻ"}
                        </span>
                      </div>
                    </div>

                    {/* Cột phải: Giá vé và trạng thái */}
                    <div className="col-auto text-end">
                      <span
                        className={`badge ${
                          entry.status === "IN" ? "bg-success" : "bg-secondary"
                        } mb-2`}
                        style={{ fontSize: "0.75rem" }}
                      >
                        {entry.status === "IN" ? "ĐANG TRONG BÃI" : "ĐÃ RA"}
                      </span>

                      {/* Giá vé */}
                      <div className="mt-2">
                        <div>
                          <div className="text-muted small">Giá vé:</div>
                          <div
                            className={
                              entry.fee > 0
                                ? "fw-bold text-success"
                                : "text-muted"
                            }
                            style={{
                              fontSize: entry.fee > 0 ? "1rem" : "0.875rem",
                            }}
                          >
                            {(entry.fee || 0).toLocaleString("vi-VN")}
                            <strong>đ</strong>
                          </div>
                        </div>
                      </div>

                      {/* Thời gian (nếu có) */}
                      {entry.duration && (
                        <div className="text-muted small mt-1">
                          <i className="bi bi-clock me-1"></i>
                          {entry.duration}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Load More Button */}
            {hasMore && (
              <div className="text-center py-3">
                <button
                  className="btn btn-outline-primary btn-sm"
                  onClick={() => fetchHistory(true)}
                  disabled={loadingMore}
                >
                  {loadingMore ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2"></span>
                      Đang tải...
                    </>
                  ) : (
                    <>
                      <i className="bi bi-arrow-down-circle me-2"></i>
                      Xem thêm
                    </>
                  )}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// ==================== Main App ====================
function App() {
  const [cameras, setCameras] = useState([]);
  const [historyKey, setHistoryKey] = useState(0);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchCameras();
    fetchStats();
    const interval = setInterval(fetchCameras, 5000);
    const statsInterval = setInterval(fetchStats, 10000);
    return () => {
      clearInterval(interval);
      clearInterval(statsInterval);
    };
  }, []);

  const fetchCameras = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/cameras`);
      const data = await response.json();
      if (data.success) {
        setCameras(data.cameras);
      }
    } catch (err) {}
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
    </div>
  );
}

export default App;
