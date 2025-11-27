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
  const [filter, setFilter] = useState("all"); // all | today | in | out

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.append("limit", "50");

      if (filter === "today") {
        params.append("today_only", "true");
      } else if (filter === "in") {
        params.append("status", "IN");
      } else if (filter === "out") {
        params.append("status", "OUT");
      }

      const response = await fetch(
        `${backendUrl}/api/parking/history?${params}`
      );
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
            <i className={`bi bi-arrow-clockwise ${loading ? "spin" : ""}`}></i>
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="card-body p-2 bg-light border-bottom">
          <div className="row g-2 text-center small">
            <div className="col">
              <div className="fw-bold text-success">
                {stats.entries_today || 0}
              </div>
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                VÀO
              </div>
            </div>
            <div className="col">
              <div className="fw-bold text-danger">
                {stats.exits_today || 0}
              </div>
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                RA
              </div>
            </div>
            <div className="col">
              <div className="fw-bold text-warning">
                {stats.vehicles_in_parking || 0}
              </div>
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                Trong bãi
              </div>
            </div>
            <div className="col">
              <div className="fw-bold text-primary">
                {((stats.revenue_today || 0) / 1000).toFixed(0)}K
              </div>
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                Thu
              </div>
            </div>
          </div>
        </div>
      )}

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
                    <div className="fw-bold text-primary">
                      {entry.plate_view}
                    </div>
                    <div className="text-muted" style={{ fontSize: "0.7rem" }}>
                      <i className="bi bi-arrow-down-circle text-success me-1"></i>
                      {entry.entry_time}
                      {entry.entry_camera_name && (
                        <span className="ms-1">
                          ({entry.entry_camera_name})
                        </span>
                      )}
                    </div>
                    {entry.exit_time && (
                      <div
                        className="text-muted"
                        style={{ fontSize: "0.7rem" }}
                      >
                        <i className="bi bi-arrow-up-circle text-danger me-1"></i>
                        {entry.exit_time}
                        {entry.exit_camera_name && (
                          <span className="ms-1">
                            ({entry.exit_camera_name})
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="text-end">
                    <span
                      className={`badge ${
                        entry.status === "IN" ? "bg-success" : "bg-secondary"
                      }`}
                    >
                      {entry.status}
                    </span>
                    {entry.duration && (
                      <div
                        className="text-muted mt-1"
                        style={{ fontSize: "0.7rem" }}
                      >
                        {entry.duration}
                      </div>
                    )}
                    {entry.fee > 0 && (
                      <div
                        className="fw-bold text-success mt-1"
                        style={{ fontSize: "0.75rem" }}
                      >
                        {entry.fee.toLocaleString("vi-VN")}đ
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
function App() {
  const [cameras, setCameras] = useState([]);
  const [historyKey, setHistoryKey] = useState(0);
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  useEffect(() => {
    fetchCameras();
    const interval = setInterval(fetchCameras, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchCameras = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/cameras`);
      const data = await response.json();
      if (data.success) {
        setCameras(data.cameras);
      }
    } catch (err) {
      console.error("Failed to fetch cameras:", err);
    }
  };

  const handleHistoryUpdate = () => {
    setHistoryKey((prev) => prev + 1);
  };

  return (
    <div
      className="d-flex flex-column"
      style={{ width: "100vw", height: "100vh", overflow: "hidden" }}
    >
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

      <div className="flex-grow-1 p-2 overflow-hidden">
        <div className="row g-2 h-100">
          {cameras.length === 0 ? (
            <div className="col-12 h-100 d-flex flex-column align-items-center justify-content-center text-muted">
              <i className="bi bi-camera-video-off fs-1 mb-2"></i>
              <div>Chưa có camera nào kết nối</div>
            </div>
          ) : (
            cameras.map((camera) => (
              <div key={camera.id} className="col-12 col-md-6 col-lg-4 h-100">
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
