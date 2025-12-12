import { useState, useEffect } from "react";
import { formatTime } from "@/utils/formatTime";

/**
 * ParkingLotView - Hiển thị tình trạng bãi đỗ xe
 * Hiển thị danh sách các camera PARKING_LOT với capacity và xe đang đỗ
 */
const ParkingLotView = ({ backendUrl }) => {
  const [parkingLots, setParkingLots] = useState([]);
  const [selectedLot, setSelectedLot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchOccupancy = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${backendUrl}/api/parking/occupancy`);
      const data = await response.json();

      if (data.success) {
        setParkingLots(data.parking_lots || []);
        // Auto-select first lot if none selected
        if (!selectedLot && data.parking_lots?.length > 0) {
          setSelectedLot(data.parking_lots[0]);
        }
      } else {
        setError(data.error || "Không thể tải dữ liệu bãi đỗ");
      }
    } catch (err) {
      console.error("Error fetching parking lot occupancy:", err);
      setError("Lỗi kết nối đến server");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Fetch once on mount
    fetchOccupancy();
  }, [backendUrl]);

  // WebSocket for real-time updates (giống HistoryPanel)
  useEffect(() => {
    const wsUrl = backendUrl.replace("http", "ws") + "/ws/history";
    let ws = null;
    let reconnectTimer = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("[ParkingLot] WebSocket connected");
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            console.log("[ParkingLot] WebSocket message received:", message);

            if (message.type === "history_update") {
              // Chỉ refetch khi có event ảnh hưởng đến occupancy
              const eventType = message.data?.event_type;
              console.log("[ParkingLot] Event type:", eventType);

              if (
                eventType === "ENTRY" ||
                eventType === "EXIT" ||
                eventType === "LOCATION_UPDATE" ||
                eventType === "PARKING_LOT_CONFIG_UPDATE"
              ) {
                console.log(
                  "[ParkingLot] Occupancy/Config changed, refetching...",
                  eventType
                );
                fetchOccupancy();
              } else {
                console.log("[ParkingLot] Event type not matched, ignoring:", eventType);
              }
            }
          } catch (err) {
            console.error("[ParkingLot] WebSocket message error:", err);
          }
        };

        ws.onclose = () => {
          console.log("[ParkingLot] WebSocket disconnected, reconnecting...");
          reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = (err) => {
          console.error("[ParkingLot] WebSocket error:", err);
        };
      } catch (err) {
        console.error("[ParkingLot] WebSocket connection error:", err);
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

  if (loading) {
    return (
      <div className="text-center py-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Đang tải...</span>
        </div>
        <p className="text-muted mt-2">Đang tải thông tin bãi đỗ...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-warning m-3" role="alert">
        <i className="bi bi-exclamation-triangle me-2"></i>
        {error}
      </div>
    );
  }

  if (parkingLots.length === 0) {
    return (
      <div className="text-center text-muted py-5">
        <i className="bi bi-inbox" style={{ fontSize: "3rem" }}></i>
        <p>Không có bãi đỗ nào</p>
        <small>Chưa có camera PARKING_LOT nào được cấu hình</small>
      </div>
    );
  }

  return (
    <div className="p-3">
      {/* List of Parking Lots */}
      <div className="row">
        {/* Left: List */}
        <div className="col-md-4">
          <h6 className="mb-3">
            <i className="bi bi-list-ul me-2"></i>
            Danh sách bãi đỗ ({parkingLots.length})
          </h6>
          <div className="list-group">
            {parkingLots.map((lot, index) => {
              const { camera, occupancy } = lot;
              const occupancyPercent =
                occupancy.total_capacity > 0
                  ? Math.round(
                      (occupancy.occupied / occupancy.total_capacity) * 100
                    )
                  : 0;

              return (
                <button
                  key={index}
                  className={`list-group-item list-group-item-action ${
                    selectedLot === lot ? "active" : ""
                  }`}
                  onClick={() => setSelectedLot(lot)}
                >
                  <div className="d-flex w-100 justify-content-between align-items-center">
                    <h6 className="mb-1">
                      <i className="bi bi-camera-video me-2"></i>
                      {camera.name}
                    </h6>
                    <span
                      className={`badge ${
                        occupancyPercent >= 90
                          ? "bg-danger"
                          : occupancyPercent >= 70
                          ? "bg-warning text-dark"
                          : "bg-success"
                      }`}
                    >
                      {occupancyPercent}%
                    </span>
                  </div>
                  <small>
                    {occupancy.occupied}/{occupancy.total_capacity} chỗ đã đỗ
                  </small>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Details */}
        <div className="col-md-8">
          {selectedLot ? (
            <ParkingLotDetails lot={selectedLot} />
          ) : (
            <div className="text-center text-muted py-5">
              <i className="bi bi-arrow-left" style={{ fontSize: "3rem" }}></i>
              <p>Chọn bãi đỗ để xem chi tiết</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Component hiển thị chi tiết 1 bãi đỗ
const ParkingLotDetails = ({ lot }) => {
  const { camera, occupancy } = lot;
  const { total_capacity, occupied, available, vehicles } = occupancy;
  const occupancyPercent =
    total_capacity > 0 ? Math.round((occupied / total_capacity) * 100) : 0;

  return (
    <div>
      {/* Header - Camera Info */}
      <div className="card mb-3 border-primary">
        <div className="card-header bg-primary text-white">
          <h6 className="mb-0">
            <i className="bi bi-camera-video me-2"></i>
            {camera.name}
          </h6>
        </div>
        <div className="card-body">
          {/* Occupancy Stats */}
          <div className="row text-center mb-3">
            <div className="col-4">
              <div className="h2 mb-0 text-primary">{total_capacity}</div>
              <small className="text-muted">Tổng số chỗ</small>
            </div>
            <div className="col-4">
              <div className="h2 mb-0 text-danger">{occupied}</div>
              <small className="text-muted">Đang đỗ</small>
            </div>
            <div className="col-4">
              <div className="h2 mb-0 text-success">{available}</div>
              <small className="text-muted">Còn trống</small>
            </div>
          </div>

          {/* Progress Bar */}
          {total_capacity > 0 && (
            <div className="mb-2">
              <div className="d-flex justify-content-between mb-1">
                <span className="small">Tỷ lệ lấp đầy</span>
                <span className="small fw-bold">{occupancyPercent}%</span>
              </div>
              <div className="progress" style={{ height: "20px" }}>
                <div
                  className={`progress-bar ${
                    occupancyPercent >= 90
                      ? "bg-danger"
                      : occupancyPercent >= 70
                      ? "bg-warning"
                      : "bg-success"
                  }`}
                  role="progressbar"
                  style={{ width: `${occupancyPercent}%` }}
                  aria-valuenow={occupancyPercent}
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  {occupancyPercent}%
                </div>
              </div>
            </div>
          )}

          {/* Warning if capacity not set */}
          {total_capacity === 0 && (
            <div className="alert alert-warning mb-0">
              <i className="bi bi-exclamation-triangle me-2"></i>
              Chưa khai báo số lượng chỗ đỗ. Vui lòng cập nhật trong Settings.
            </div>
          )}
        </div>
      </div>

      {/* Vehicle List */}
      <div className="card border-secondary">
        <div className="card-header bg-secondary text-white">
          <h6 className="mb-0">
            <i className="bi bi-car-front me-2"></i>
            Danh sách xe đang đỗ ({occupied})
          </h6>
        </div>
        <div className="card-body p-0">
          {vehicles.length === 0 ? (
            <div className="text-center text-muted py-4">
              <i className="bi bi-inbox" style={{ fontSize: "2rem" }}></i>
              <p className="mb-0 mt-2">Chưa có xe nào trong bãi</p>
            </div>
          ) : (
            <div className="list-group list-group-flush">
              {vehicles.map((vehicle, index) => (
                <div
                  key={index}
                  className="list-group-item d-flex justify-content-between align-items-center"
                >
                  <div>
                    <div className="d-flex align-items-center gap-2">
                      <span className="badge bg-primary">
                        {vehicle.plate_view}
                      </span>
                      {vehicle.is_anomaly && (
                        <span
                          className="badge bg-warning text-dark"
                          title="Xe này được phát hiện tự động bởi camera PARKING_LOT (không có entry record)"
                        >
                          <i className="bi bi-exclamation-triangle"></i>
                        </span>
                      )}
                    </div>
                    <small className="text-muted d-block mt-1">
                      <i className="bi bi-clock me-1"></i>
                      Vào lúc: {formatTime(new Date(vehicle.entry_time))}
                    </small>
                    {vehicle.location_time && (
                      <small className="text-muted d-block">
                        <i className="bi bi-geo-alt me-1"></i>
                        Cập nhật vị trí:{" "}
                        {formatTime(new Date(vehicle.location_time))}
                      </small>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ParkingLotView;
