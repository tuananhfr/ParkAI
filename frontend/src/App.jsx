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
    const wsUrl = backendUrl.replace("http", "ws") + "/ws/history";
    let ws = null;
    let reconnectTimer = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("[History] WebSocket connected");
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            if (message.type === "history_update") {
              // Fetch latest entry from database
              fetchHistory();
            }
          } catch (err) {
            console.error("[History] WebSocket message error:", err);
          }
        };

        ws.onclose = () => {
          console.log("[History] WebSocket disconnected, reconnecting...");
          reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = (err) => {
          console.error("[History] WebSocket error:", err);
        };
      } catch (err) {
        console.error("[History] WebSocket connection error:", err);
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
                <div
                  key={entry.id}
                  className="list-group-item p-2 border-bottom"
                >
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

// ==================== Subscription Dev Mode Component ====================
const SubscriptionDevMode = ({ apiUrl, onSave }) => {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState({
    plate_number: "",
    owner_name: "",
    type: "company",
    status: "active",
    start_date: "",
    end_date: "",
    phone: "",
    note: "",
  });

  useEffect(() => {
    fetchSubscriptions();
  }, [apiUrl]);

  const fetchSubscriptions = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${CENTRAL_URL}/api/subscriptions`);
      const data = await response.json();
      if (data.success) {
        setSubscriptions(data.subscriptions || []);
      } else {
        setError(data.error || "Không thể tải danh sách thuê bao");
      }
    } catch (err) {
      setError("Không thể kết nối đến server");
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (sub) => {
    setEditingId(sub.id);
    setFormData({
      plate_number: sub.plate_number || "",
      owner_name: sub.owner_name || "",
      type: sub.type || "company",
      status: sub.status || "active",
      start_date: sub.start_date || "",
      end_date: sub.end_date || "",
      phone: sub.phone || "",
      note: sub.note || "",
    });
    setShowAddForm(false);
  };

  const handleAdd = () => {
    setEditingId(null);
    setFormData({
      plate_number: "",
      owner_name: "",
      type: "company",
      status: "active",
      start_date: "",
      end_date: "",
      phone: "",
      note: "",
    });
    setShowAddForm(true);
  };

  const handleDelete = (id) => {
    if (window.confirm("Bạn có chắc muốn xóa thuê bao này?")) {
      setSubscriptions(subscriptions.filter((sub) => sub.id !== id));
    }
  };

  const handleSaveForm = () => {
    if (!formData.plate_number.trim()) {
      alert("Vui lòng nhập biển số xe");
      return;
    }

    if (editingId) {
      // Update existing
      setSubscriptions(
        subscriptions.map((sub) =>
          sub.id === editingId
            ? {
                ...sub,
                ...formData,
              }
            : sub
        )
      );
      setEditingId(null);
    } else {
      // Add new
      const maxId =
        subscriptions.length > 0
          ? Math.max(...subscriptions.map((s) => s.id || 0))
          : 0;
      setSubscriptions([
        ...subscriptions,
        {
          id: maxId + 1,
          ...formData,
        },
      ]);
      setShowAddForm(false);
    }
    setFormData({
      plate_number: "",
      owner_name: "",
      type: "company",
      status: "active",
      start_date: "",
      end_date: "",
      phone: "",
      note: "",
    });
  };

  const handleSaveToServer = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/subscriptions`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subscriptions }),
      });
      const data = await response.json();
      if (data.success) {
        alert("Đã lưu thành công!");
        fetchSubscriptions();
        if (onSave) onSave();
      } else {
        alert(`Lỗi: ${data.error || "Không thể lưu"}`);
      }
    } catch (err) {
      alert("Không thể kết nối đến server");
    }
  };

  const getTypeLabel = (type) => {
    switch (type) {
      case "company":
        return "Thẻ công ty";
      case "monthly":
        return "Thẻ tháng";
      case "regular":
        return "Khách lẻ";
      default:
        return type;
    }
  };

  const getTypeBadge = (type) => {
    switch (type) {
      case "company":
        return "bg-primary";
      case "monthly":
        return "bg-info";
      case "regular":
        return "bg-warning";
      default:
        return "bg-secondary";
    }
  };

  if (loading) {
    return (
      <div className="text-center py-3">
        <div className="spinner-border spinner-border-sm text-primary"></div>
        <small className="d-block mt-2 text-muted">Đang tải...</small>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-warning">
        <i className="bi bi-exclamation-triangle me-2"></i>
        {error}
      </div>
    );
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <small className="text-muted">
          <i className="bi bi-info-circle me-1"></i>
          Tổng số: {subscriptions.length} thuê bao
        </small>
        <button
          className="btn btn-sm btn-success"
          onClick={handleAdd}
          disabled={showAddForm || editingId !== null}
        >
          <i className="bi bi-plus-circle me-1"></i>
          Thêm mới
        </button>
      </div>

      {showAddForm && (
        <div className="card mb-3 border-success">
          <div className="card-header bg-success text-white">
            <strong>Thêm thuê bao mới</strong>
          </div>
          <div className="card-body">
            <div className="row g-2">
              <div className="col-md-6">
                <label className="form-label small">Biển số xe *</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={formData.plate_number}
                  onChange={(e) =>
                    setFormData({ ...formData, plate_number: e.target.value })
                  }
                  placeholder="30A12345"
                />
              </div>
              <div className="col-md-6">
                <label className="form-label small">Tên chủ xe</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={formData.owner_name}
                  onChange={(e) =>
                    setFormData({ ...formData, owner_name: e.target.value })
                  }
                  placeholder="Nguyễn Văn A"
                />
              </div>
              <div className="col-md-4">
                <label className="form-label small">Loại</label>
                <select
                  className="form-select form-select-sm"
                  value={formData.type}
                  onChange={(e) =>
                    setFormData({ ...formData, type: e.target.value })
                  }
                >
                  <option value="company">Thẻ công ty</option>
                  <option value="monthly">Thẻ tháng</option>
                  <option value="regular">Khách lẻ</option>
                </select>
              </div>
              <div className="col-md-4">
                <label className="form-label small">Trạng thái</label>
                <select
                  className="form-select form-select-sm"
                  value={formData.status}
                  onChange={(e) =>
                    setFormData({ ...formData, status: e.target.value })
                  }
                >
                  <option value="active">Hoạt động</option>
                  <option value="inactive">Nghỉ</option>
                </select>
              </div>
              <div className="col-md-4">
                <label className="form-label small">Số điện thoại</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={formData.phone}
                  onChange={(e) =>
                    setFormData({ ...formData, phone: e.target.value })
                  }
                  placeholder="0901234567"
                />
              </div>
              {(formData.type === "company" || formData.type === "monthly") && (
                <>
                  <div className="col-md-6">
                    <label className="form-label small">Ngày bắt đầu</label>
                    <input
                      type="date"
                      className="form-control form-control-sm"
                      value={formData.start_date}
                      onChange={(e) =>
                        setFormData({ ...formData, start_date: e.target.value })
                      }
                    />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label small">Ngày kết thúc</label>
                    <input
                      type="date"
                      className="form-control form-control-sm"
                      value={formData.end_date}
                      onChange={(e) =>
                        setFormData({ ...formData, end_date: e.target.value })
                      }
                    />
                  </div>
                </>
              )}
              <div className="col-12">
                <label className="form-label small">Ghi chú</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={formData.note}
                  onChange={(e) =>
                    setFormData({ ...formData, note: e.target.value })
                  }
                  placeholder="Ghi chú"
                />
              </div>
            </div>
            <div className="mt-3">
              <button
                className="btn btn-sm btn-primary me-2"
                onClick={handleSaveForm}
              >
                <i className="bi bi-check-circle me-1"></i>
                Lưu
              </button>
              <button
                className="btn btn-sm btn-secondary"
                onClick={() => {
                  setShowAddForm(false);
                  setFormData({
                    plate_number: "",
                    owner_name: "",
                    type: "company",
                    status: "active",
                    start_date: "",
                    end_date: "",
                    phone: "",
                    note: "",
                  });
                }}
              >
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="table-responsive">
        <table className="table table-sm table-striped table-hover">
          <thead>
            <tr>
              <th>ID</th>
              <th>Biển số</th>
              <th>Chủ xe</th>
              <th>Loại</th>
              <th>SĐT</th>
              <th>Trạng thái</th>
              <th>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) =>
              editingId === sub.id ? (
                <tr key={sub.id} className="table-warning">
                  <td colSpan="7">
                    <div className="row g-2">
                      <div className="col-md-6">
                        <label className="form-label small">Biển số xe *</label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={formData.plate_number}
                          onChange={(e) =>
                            setFormData({
                              ...formData,
                              plate_number: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div className="col-md-6">
                        <label className="form-label small">Tên chủ xe</label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={formData.owner_name}
                          onChange={(e) =>
                            setFormData({
                              ...formData,
                              owner_name: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div className="col-md-4">
                        <label className="form-label small">Loại</label>
                        <select
                          className="form-select form-select-sm"
                          value={formData.type}
                          onChange={(e) =>
                            setFormData({ ...formData, type: e.target.value })
                          }
                        >
                          <option value="company">Thẻ công ty</option>
                          <option value="monthly">Thẻ tháng</option>
                          <option value="regular">Khách lẻ</option>
                        </select>
                      </div>
                      <div className="col-md-4">
                        <label className="form-label small">Trạng thái</label>
                        <select
                          className="form-select form-select-sm"
                          value={formData.status}
                          onChange={(e) =>
                            setFormData({
                              ...formData,
                              status: e.target.value,
                            })
                          }
                        >
                          <option value="active">Hoạt động</option>
                          <option value="inactive">Nghỉ</option>
                        </select>
                      </div>
                      <div className="col-md-4">
                        <label className="form-label small">
                          Số điện thoại
                        </label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={formData.phone}
                          onChange={(e) =>
                            setFormData({ ...formData, phone: e.target.value })
                          }
                        />
                      </div>
                      {(formData.type === "company" ||
                        formData.type === "monthly") && (
                        <>
                          <div className="col-md-6">
                            <label className="form-label small">
                              Ngày bắt đầu
                            </label>
                            <input
                              type="date"
                              className="form-control form-control-sm"
                              value={formData.start_date}
                              onChange={(e) =>
                                setFormData({
                                  ...formData,
                                  start_date: e.target.value,
                                })
                              }
                            />
                          </div>
                          <div className="col-md-6">
                            <label className="form-label small">
                              Ngày kết thúc
                            </label>
                            <input
                              type="date"
                              className="form-control form-control-sm"
                              value={formData.end_date}
                              onChange={(e) =>
                                setFormData({
                                  ...formData,
                                  end_date: e.target.value,
                                })
                              }
                            />
                          </div>
                        </>
                      )}
                      <div className="col-12">
                        <label className="form-label small">Ghi chú</label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={formData.note}
                          onChange={(e) =>
                            setFormData({ ...formData, note: e.target.value })
                          }
                        />
                      </div>
                      <div className="col-12">
                        <button
                          className="btn btn-sm btn-primary me-2"
                          onClick={handleSaveForm}
                        >
                          <i className="bi bi-check-circle me-1"></i>
                          Lưu
                        </button>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={() => {
                            setEditingId(null);
                            setFormData({
                              plate_number: "",
                              owner_name: "",
                              type: "company",
                              status: "active",
                              start_date: "",
                              end_date: "",
                              phone: "",
                              note: "",
                            });
                          }}
                        >
                          Hủy
                        </button>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={sub.id}>
                  <td>{sub.id}</td>
                  <td>
                    <strong>{sub.plate_number}</strong>
                  </td>
                  <td>{sub.owner_name || "-"}</td>
                  <td>
                    <span className={`badge ${getTypeBadge(sub.type)}`}>
                      {getTypeLabel(sub.type)}
                    </span>
                  </td>
                  <td>{sub.phone || "-"}</td>
                  <td>
                    <span
                      className={`badge ${
                        sub.status === "active" ? "bg-success" : "bg-secondary"
                      }`}
                    >
                      {sub.status === "active" ? "Hoạt động" : "Nghỉ"}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn btn-sm btn-outline-primary me-1"
                      onClick={() => handleEdit(sub)}
                      title="Sửa"
                    >
                      <i className="bi bi-pencil"></i>
                    </button>
                    <button
                      className="btn btn-sm btn-outline-danger"
                      onClick={() => handleDelete(sub.id)}
                      title="Xóa"
                    >
                      <i className="bi bi-trash"></i>
                    </button>
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-3 d-flex justify-content-end">
        <button className="btn btn-primary btn-sm" onClick={handleSaveToServer}>
          <i className="bi bi-save me-1"></i>
          Lưu vào file JSON
        </button>
      </div>
    </div>
  );
};

// ==================== Central Sync Servers List Component ====================
const CentralSyncServersList = ({ config, updateConfig }) => {
  const [servers, setServers] = useState([]);
  const [newServer, setNewServer] = useState("");

  useEffect(() => {
    const syncServers = config.central_sync?.servers || [];
    setServers(Array.isArray(syncServers) ? syncServers : []);
  }, [config.central_sync?.servers]);

  const handleAddServer = () => {
    if (newServer.trim() && !servers.includes(newServer.trim())) {
      const updated = [...servers, newServer.trim()];
      setServers(updated);
      updateConfig("central_sync", "servers", updated);
      setNewServer("");
    }
  };

  const handleRemoveServer = (index) => {
    const updated = servers.filter((_, i) => i !== index);
    setServers(updated);
    updateConfig("central_sync", "servers", updated);
  };

  return (
    <div>
      <div className="d-flex gap-2 mb-2">
        <input
          type="text"
          className="form-control form-control-sm"
          value={newServer}
          onChange={(e) => setNewServer(e.target.value)}
          placeholder="http://192.168.1.101:8000"
          onKeyPress={(e) => {
            if (e.key === "Enter") {
              handleAddServer();
            }
          }}
        />
        <button
          className="btn btn-sm btn-primary"
          onClick={handleAddServer}
          disabled={!newServer.trim()}
        >
          <i className="bi bi-plus-circle me-1"></i>
          Thêm
        </button>
      </div>
      {servers.length === 0 ? (
        <div className="alert alert-info">
          <i className="bi bi-info-circle me-2"></i>
          Chưa có máy chủ central nào được cấu hình
        </div>
      ) : (
        <div className="list-group">
          {servers.map((server, index) => (
            <div
              key={index}
              className="list-group-item d-flex justify-content-between align-items-center"
            >
              <span>
                <i className="bi bi-server me-2"></i>
                {server}
              </span>
              <button
                className="btn btn-sm btn-outline-danger"
                onClick={() => handleRemoveServer(index)}
                title="Xóa"
              >
                <i className="bi bi-trash"></i>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ==================== Subscription List Component ====================
const SubscriptionList = ({ apiUrl }) => {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchSubscriptions();
  }, [apiUrl]);

  const fetchSubscriptions = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${CENTRAL_URL}/api/subscriptions`);
      const data = await response.json();
      if (data.success) {
        setSubscriptions(data.subscriptions || []);
      } else {
        setError(data.error || "Không thể tải danh sách thuê bao");
      }
    } catch (err) {
      setError("Không thể kết nối đến server");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-3">
        <div className="spinner-border spinner-border-sm text-primary"></div>
        <small className="d-block mt-2 text-muted">Đang tải...</small>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-warning">
        <i className="bi bi-exclamation-triangle me-2"></i>
        {error}
      </div>
    );
  }

  if (!subscriptions || subscriptions.length === 0) {
    return (
      <div className="alert alert-info">
        <i className="bi bi-info-circle me-2"></i>
        Chưa có dữ liệu thuê bao
      </div>
    );
  }

  const getTypeLabel = (type) => {
    switch (type) {
      case "company":
        return "Thẻ công ty";
      case "monthly":
        return "Thẻ tháng";
      case "regular":
        return "Khách lẻ";
      default:
        return type;
    }
  };

  const getTypeBadge = (type) => {
    switch (type) {
      case "company":
        return "bg-primary";
      case "monthly":
        return "bg-info";
      case "regular":
        return "bg-warning";
      default:
        return "bg-secondary";
    }
  };

  return (
    <div>
      <div className="mb-2">
        <small className="text-muted">
          <i className="bi bi-info-circle me-1"></i>
          Tổng số: {subscriptions.length} thuê bao
        </small>
      </div>
      <div className="table-responsive">
        <table className="table table-sm table-striped table-hover">
          <thead>
            <tr>
              <th>Biển số</th>
              <th>Chủ xe</th>
              <th>Loại</th>
              <th>SĐT</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) => (
              <tr key={sub.id}>
                <td>
                  <strong>{sub.plate_number}</strong>
                </td>
                <td>{sub.owner_name || "-"}</td>
                <td>
                  <span className={`badge ${getTypeBadge(sub.type)}`}>
                    {getTypeLabel(sub.type)}
                  </span>
                </td>
                <td>{sub.phone || "-"}</td>
                <td>
                  <span
                    className={`badge ${
                      sub.status === "active" ? "bg-success" : "bg-secondary"
                    }`}
                  >
                    {sub.status === "active" ? "Hoạt động" : "Nghỉ"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ==================== Staff List Component ====================
const StaffList = ({ apiUrl }) => {
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStaff();
  }, [apiUrl]);

  const fetchStaff = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${CENTRAL_URL}/api/staff`);
      const data = await response.json();
      if (data.success) {
        setStaff(data.staff || []);
      } else {
        setError(data.error || "Không thể tải danh sách người trực");
      }
    } catch (err) {
      setError("Không thể kết nối đến server");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-3">
        <div className="spinner-border spinner-border-sm text-primary"></div>
        <small className="d-block mt-2 text-muted">Đang tải...</small>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-warning">
        <i className="bi bi-exclamation-triangle me-2"></i>
        {error}
      </div>
    );
  }

  if (!staff || staff.length === 0) {
    return (
      <div className="alert alert-info">
        <i className="bi bi-info-circle me-2"></i>
        Chưa có dữ liệu người trực
      </div>
    );
  }

  return (
    <div>
      <div className="mb-2">
        <small className="text-muted">
          <i className="bi bi-info-circle me-1"></i>
          Tổng số: {staff.length} người trực
        </small>
      </div>
      <div className="table-responsive">
        <table className="table table-sm table-striped table-hover">
          <thead>
            <tr>
              <th>ID</th>
              <th>Tên</th>
              <th>Chức vụ</th>
              <th>Số điện thoại</th>
              <th>Ca trực</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {staff.map((person) => (
              <tr key={person.id}>
                <td>{person.id}</td>
                <td>{person.name}</td>
                <td>{person.position || "-"}</td>
                <td>{person.phone || "-"}</td>
                <td>
                  <span
                    className={`badge ${
                      person.shift === "Ca ngày"
                        ? "bg-info"
                        : person.shift === "Ca đêm"
                        ? "bg-dark"
                        : "bg-secondary"
                    }`}
                  >
                    {person.shift || "-"}
                  </span>
                </td>
                <td>
                  <span
                    className={`badge ${
                      person.status === "active" ? "bg-success" : "bg-secondary"
                    }`}
                  >
                    {person.status === "active" ? "Hoạt động" : "Nghỉ"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ==================== Settings Modal ====================
const SettingsModal = ({ show, onClose, onSaveSuccess }) => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [activeTab, setActiveTab] = useState("parking"); // parking, cameras, staff, subscriptions, report, central_server, central_sync, card_reader, barrier
  const [showAddCameraForm, setShowAddCameraForm] = useState(false);
  const [subscriptionDevMode, setSubscriptionDevMode] = useState(false);
  const [newCamera, setNewCamera] = useState({
    name: "",
    ip: "",
    camera_type: "ENTRY",
  });

  useEffect(() => {
    if (show) {
      fetchConfig();
      // Reset form khi mở modal
      setActiveTab("parking"); // Reset về tab đầu tiên
      setShowAddCameraForm(false);
      setNewCamera({
        name: "",
        ip: "",
        camera_type: "ENTRY",
      });
      setMessage(null);
    }
  }, [show]);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${CENTRAL_URL}/api/config`);
      const data = await response.json();
      if (data.success) {
        setConfig(data.config);
      }
    } catch (err) {
      setMessage({ type: "error", text: "Không thể tải cấu hình" });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await fetch(`${CENTRAL_URL}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await response.json();
      if (data.success) {
        // Đóng modal ngay lập tức và reload cameras
        onClose();
        // Reload cameras để cập nhật tên mới
        if (typeof onSaveSuccess === "function") {
          onSaveSuccess();
        }
      } else {
        setMessage({
          type: "error",
          text: `❌ ${data.error || "Lỗi lưu cấu hình"}`,
        });
      }
    } catch (err) {
      setMessage({ type: "error", text: "❌ Không thể lưu cấu hình" });
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = (section, key, value) => {
    setConfig((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value,
      },
    }));
  };

  const updateCameraConfig = (camId, key, value) => {
    setConfig((prev) => ({
      ...prev,
      edge_cameras: {
        ...prev.edge_cameras,
        [camId]: {
          ...prev.edge_cameras[camId],
          [key]: value,
        },
      },
    }));
  };

  const handleAddCamera = () => {
    if (!newCamera.name.trim() || !newCamera.ip.trim()) {
      setMessage({
        type: "error",
        text: "Vui lòng điền đầy đủ tên camera và IP address",
      });
      return;
    }

    // Validate IP format cơ bản
    const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipPattern.test(newCamera.ip.trim())) {
      setMessage({
        type: "error",
        text: "IP address không hợp lệ. Vui lòng nhập đúng định dạng (ví dụ: 192.168.0.144)",
      });
      return;
    }

    // Tìm camera ID lớn nhất và tăng lên 1
    const existingIds = Object.keys(config.edge_cameras || {})
      .map((id) => parseInt(id, 10))
      .filter((id) => !isNaN(id));
    const maxId = existingIds.length > 0 ? Math.max(...existingIds) : 0;
    const newCameraId = maxId + 1;

    // Thêm camera mới vào config
    setConfig((prev) => ({
      ...prev,
      edge_cameras: {
        ...prev.edge_cameras,
        [newCameraId]: {
          name: newCamera.name.trim(),
          ip: newCamera.ip.trim(),
          camera_type: newCamera.camera_type || "ENTRY",
        },
      },
    }));

    // Reset form
    setNewCamera({
      name: "",
      ip: "",
      camera_type: "ENTRY",
    });
    setShowAddCameraForm(false);
    setMessage({
      type: "success",
      text: `Đã thêm camera ${newCameraId}: ${newCamera.name.trim()}`,
    });
  };

  const handleRemoveCamera = (camId) => {
    if (
      window.confirm(
        `Bạn có chắc muốn xóa camera ${camId}: ${
          config.edge_cameras[camId]?.name || ""
        }?`
      )
    ) {
      setConfig((prev) => {
        const newCameras = { ...prev.edge_cameras };
        delete newCameras[camId];
        return {
          ...prev,
          edge_cameras: newCameras,
        };
      });
      setMessage({
        type: "success",
        text: `Đã xóa camera ${camId}`,
      });
    }
  };

  if (!show) return null;

  return (
    <div
      className="modal show d-block"
      style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
      onClick={onClose}
    >
      <div
        className="modal-dialog modal-xl modal-dialog-scrollable"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-content">
          <div className="modal-header bg-primary text-white">
            <h5 className="modal-title">
              <i className="bi bi-gear-fill me-2"></i>
              Cài đặt hệ thống
            </h5>
            <button
              type="button"
              className="btn-close btn-close-white"
              onClick={onClose}
            ></button>
          </div>
          <div className="modal-body">
            {loading ? (
              <div className="text-center py-4">
                <div className="spinner-border text-primary"></div>
              </div>
            ) : config ? (
              <div>
                {message && (
                  <div
                    className={`alert alert-${
                      message.type === "success" ? "success" : "danger"
                    }`}
                  >
                    {message.text}
                  </div>
                )}

                {/* Tab Navigation */}
                <ul className="nav nav-tabs mb-3" role="tablist">
                  <li className="nav-item" role="presentation">
                    <button
                      className={`nav-link ${
                        activeTab === "parking" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("parking")}
                      type="button"
                    >
                      <i className="bi bi-cash-coin me-2"></i>
                      Phí gửi xe
                    </button>
                  </li>
                  <li className="nav-item" role="presentation">
                    <button
                      className={`nav-link ${
                        activeTab === "cameras" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("cameras")}
                      type="button"
                    >
                      <i className="bi bi-camera-video me-2"></i>
                      Cameras
                    </button>
                  </li>
                  <li className="nav-item" role="presentation">
                    <button
                      className={`nav-link ${
                        activeTab === "staff" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("staff")}
                      type="button"
                    >
                      <i className="bi bi-people me-2"></i>
                      Danh sách người trực
                    </button>
                  </li>
                  <li className="nav-item" role="presentation">
                    <button
                      className={`nav-link ${
                        activeTab === "subscriptions" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("subscriptions")}
                      type="button"
                    >
                      <i className="bi bi-card-list me-2"></i>
                      Danh sách thuê bao
                    </button>
                  </li>
                  <li className="nav-item" role="presentation">
                    <button
                      className={`nav-link ${
                        activeTab === "card_reader" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("card_reader")}
                      type="button"
                    >
                      <i className="bi bi-credit-card me-2"></i>
                      Đọc thẻ từ
                    </button>
                  </li>
                  <li className="nav-item" role="presentation">
                    <button
                      className={`nav-link ${
                        activeTab === "report" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("report")}
                      type="button"
                    >
                      <i className="bi bi-file-earmark-text me-2"></i>
                      Gửi báo cáo
                    </button>
                  </li>
                  <li className="nav-item" role="presentation">
                    <button
                      className={`nav-link ${
                        activeTab === "central_server" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("central_server")}
                      type="button"
                    >
                      <i className="bi bi-server me-2"></i>
                      IP máy chủ central
                    </button>
                  </li>
                  <li className="nav-item" role="presentation">
                    <button
                      className={`nav-link ${
                        activeTab === "central_sync" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("central_sync")}
                      type="button"
                    >
                      <i className="bi bi-arrow-repeat me-2"></i>
                      IP máy chủ central khác
                    </button>
                  </li>
                  <li className="nav-item" role="presentation">
                    <button
                      className={`nav-link ${
                        activeTab === "barrier" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("barrier")}
                      type="button"
                    >
                      <i className="bi bi-radioactive me-2"></i>
                      Barrier hồng ngoại
                    </button>
                  </li>
                </ul>

                {/* Tab Content */}
                {activeTab === "parking" && (
                  <div>
                    {/* Parking Fees */}
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-cash-coin me-2"></i>
                      Phí gửi xe
                    </h6>
                    <div className="row g-3 mb-4">
                      <div className="col-md-6">
                        <label className="form-label small">
                          Phí cơ bản (2h đầu)
                        </label>
                        <div className="input-group input-group-sm">
                          <input
                            type="number"
                            className="form-control"
                            value={config.parking.fee_base}
                            onChange={(e) =>
                              updateConfig(
                                "parking",
                                "fee_base",
                                parseInt(e.target.value)
                              )
                            }
                          />
                          <span className="input-group-text">đ</span>
                        </div>
                      </div>
                      <div className="col-md-6">
                        <label className="form-label small">
                          Phí mỗi giờ sau đó
                        </label>
                        <div className="input-group input-group-sm">
                          <input
                            type="number"
                            className="form-control"
                            value={config.parking.fee_per_hour}
                            onChange={(e) =>
                              updateConfig(
                                "parking",
                                "fee_per_hour",
                                parseInt(e.target.value)
                              )
                            }
                          />
                          <span className="input-group-text">đ</span>
                        </div>
                      </div>
                      <div className="col-md-6">
                        <label className="form-label small">
                          Phí qua đêm (22h-6h)
                        </label>
                        <div className="input-group input-group-sm">
                          <input
                            type="number"
                            className="form-control"
                            value={config.parking.fee_overnight}
                            onChange={(e) =>
                              updateConfig(
                                "parking",
                                "fee_overnight",
                                parseInt(e.target.value)
                              )
                            }
                          />
                          <span className="input-group-text">đ</span>
                        </div>
                      </div>
                      <div className="col-md-6">
                        <label className="form-label small">
                          Phí tối đa 1 ngày
                        </label>
                        <div className="input-group input-group-sm">
                          <input
                            type="number"
                            className="form-control"
                            value={config.parking.fee_daily_max}
                            onChange={(e) =>
                              updateConfig(
                                "parking",
                                "fee_daily_max",
                                parseInt(e.target.value)
                              )
                            }
                          />
                          <span className="input-group-text">đ</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "cameras" && (
                  <div>
                    {/* Camera Settings */}
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-camera-video me-2"></i>
                      Cấu hình Camera
                    </h6>
                    <div className="mb-3">
                      <label className="form-label small">
                        Heartbeat Timeout (giây)
                      </label>
                      <input
                        type="number"
                        className="form-control form-control-sm"
                        value={config.camera.heartbeat_timeout}
                        onChange={(e) =>
                          updateConfig(
                            "camera",
                            "heartbeat_timeout",
                            parseInt(e.target.value)
                          )
                        }
                      />
                    </div>

                    {/* Edge Cameras */}
                    <div className="d-flex justify-content-between align-items-center mb-3">
                      <h6 className="border-bottom pb-2 mb-0">
                        <i className="bi bi-hdd-network me-2"></i>
                        Edge Cameras
                      </h6>
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => setShowAddCameraForm(!showAddCameraForm)}
                      >
                        <i className="bi bi-plus-circle me-1"></i>
                        Thêm camera
                      </button>
                    </div>

                    {/* Form thêm camera mới */}
                    {showAddCameraForm && (
                      <div className="card mb-3 border-primary">
                        <div className="card-body">
                          <h6 className="card-title text-primary">
                            <i className="bi bi-plus-circle me-2"></i>
                            Thêm camera mới
                          </h6>
                          <div className="row g-2">
                            <div className="col-md-5">
                              <label className="form-label small">
                                Tên camera{" "}
                                <span className="text-danger">*</span>
                              </label>
                              <input
                                type="text"
                                className="form-control form-control-sm"
                                value={newCamera.name}
                                onChange={(e) =>
                                  setNewCamera({
                                    ...newCamera,
                                    name: e.target.value,
                                  })
                                }
                                placeholder="Cổng vào B"
                              />
                            </div>
                            <div className="col-md-4">
                              <label className="form-label small">
                                IP Address{" "}
                                <span className="text-danger">*</span>
                              </label>
                              <input
                                type="text"
                                className="form-control form-control-sm"
                                value={newCamera.ip}
                                onChange={(e) =>
                                  setNewCamera({
                                    ...newCamera,
                                    ip: e.target.value,
                                  })
                                }
                                placeholder="192.168.0.145"
                              />
                            </div>
                            <div className="col-md-3">
                              <label className="form-label small">
                                Loại cổng
                              </label>
                              <select
                                className="form-select form-select-sm"
                                value={newCamera.camera_type}
                                onChange={(e) =>
                                  setNewCamera({
                                    ...newCamera,
                                    camera_type: e.target.value,
                                  })
                                }
                              >
                                <option value="ENTRY">VÀO</option>
                                <option value="EXIT">RA</option>
                              </select>
                            </div>
                          </div>
                          <div className="mt-2 d-flex gap-2">
                            <button
                              className="btn btn-sm btn-success"
                              onClick={handleAddCamera}
                            >
                              <i className="bi bi-check-circle me-1"></i>
                              Thêm
                            </button>
                            <button
                              className="btn btn-sm btn-secondary"
                              onClick={() => {
                                setShowAddCameraForm(false);
                                setNewCamera({
                                  name: "",
                                  ip: "",
                                  camera_type: "ENTRY",
                                });
                              }}
                            >
                              <i className="bi bi-x-circle me-1"></i>
                              Hủy
                            </button>
                          </div>
                        </div>
                      </div>
                    )}

                    {Object.entries(config.edge_cameras)
                      .sort(([a], [b]) => parseInt(a, 10) - parseInt(b, 10))
                      .map(([camId, camConfig]) => (
                        <div key={camId} className="card mb-3">
                          <div className="card-body">
                            <div className="d-flex justify-content-between align-items-start mb-2">
                              <h6 className="card-title mb-0">
                                <span className="badge bg-primary me-2">
                                  Camera {camId}
                                </span>
                                {camConfig.name}
                                <span
                                  className={`badge ${
                                    camConfig.camera_type === "ENTRY"
                                      ? "bg-success"
                                      : "bg-danger"
                                  } ms-2`}
                                >
                                  {camConfig.camera_type === "ENTRY"
                                    ? "VÀO"
                                    : "RA"}
                                </span>
                              </h6>
                              <button
                                className="btn btn-sm btn-outline-danger"
                                onClick={() => handleRemoveCamera(camId)}
                                title="Xóa camera"
                              >
                                <i className="bi bi-trash"></i>
                              </button>
                            </div>
                            <div className="row g-2">
                              <div className="col-md-5">
                                <label className="form-label small">
                                  Tên camera
                                </label>
                                <input
                                  type="text"
                                  className="form-control form-control-sm"
                                  value={camConfig.name}
                                  onChange={(e) =>
                                    updateCameraConfig(
                                      camId,
                                      "name",
                                      e.target.value
                                    )
                                  }
                                  placeholder="Cổng vào A"
                                />
                              </div>
                              <div className="col-md-4">
                                <label className="form-label small">
                                  IP Address
                                </label>
                                <input
                                  type="text"
                                  className="form-control form-control-sm"
                                  value={camConfig.ip}
                                  onChange={(e) =>
                                    updateCameraConfig(
                                      camId,
                                      "ip",
                                      e.target.value
                                    )
                                  }
                                  placeholder="192.168.0.144"
                                />
                              </div>
                              <div className="col-md-3">
                                <label className="form-label small">
                                  Loại cổng
                                </label>
                                <select
                                  className="form-select form-select-sm"
                                  value={camConfig.camera_type || "ENTRY"}
                                  onChange={(e) =>
                                    updateCameraConfig(
                                      camId,
                                      "camera_type",
                                      e.target.value
                                    )
                                  }
                                >
                                  <option value="ENTRY">VÀO</option>
                                  <option value="EXIT">RA</option>
                                </select>
                              </div>
                            </div>
                            <div className="mt-2">
                              <small className="text-muted">
                                <i className="bi bi-info-circle me-1"></i>
                                URLs được tự động tạo: http://{camConfig.ip}
                                :5000
                              </small>
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                )}

                {activeTab === "staff" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-people me-2"></i>
                      Danh sách người trực
                    </h6>
                    <div className="mb-3">
                      <label className="form-label small">
                        API Endpoint (để trống sẽ dùng file JSON)
                      </label>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        value={config.staff?.api_url || ""}
                        onChange={(e) =>
                          updateConfig("staff", "api_url", e.target.value)
                        }
                        placeholder="https://api.example.com/staff"
                      />
                      <small className="text-muted">
                        <i className="bi bi-info-circle me-1"></i>
                        Nếu để trống, hệ thống sẽ sử dụng file JSON local
                      </small>
                    </div>
                    <div className="mt-4">
                      <StaffList apiUrl={config.staff?.api_url || ""} />
                    </div>
                  </div>
                )}

                {activeTab === "subscriptions" && (
                  <div>
                    <div className="d-flex justify-content-between align-items-center mb-3">
                      <h6 className="border-bottom pb-2 mb-0">
                        <i className="bi bi-card-list me-2"></i>
                        Danh sách thuê bao
                      </h6>
                      <button
                        className={`btn btn-sm ${
                          subscriptionDevMode
                            ? "btn-warning"
                            : "btn-outline-secondary"
                        }`}
                        onClick={() =>
                          setSubscriptionDevMode(!subscriptionDevMode)
                        }
                      >
                        <i
                          className={`bi ${
                            subscriptionDevMode
                              ? "bi-toggle-on"
                              : "bi-toggle-off"
                          } me-1`}
                        ></i>
                        Dev Mode
                      </button>
                    </div>
                    {!subscriptionDevMode && (
                      <div className="mb-3">
                        <label className="form-label small">
                          API Endpoint (để trống sẽ dùng file JSON)
                        </label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={config.subscriptions?.api_url || ""}
                          onChange={(e) =>
                            updateConfig(
                              "subscriptions",
                              "api_url",
                              e.target.value
                            )
                          }
                          placeholder="https://api.example.com/subscriptions"
                        />
                        <small className="text-muted">
                          <i className="bi bi-info-circle me-1"></i>
                          Nếu để trống, hệ thống sẽ sử dụng file JSON local
                        </small>
                      </div>
                    )}
                    <div className="mt-4">
                      {subscriptionDevMode ? (
                        <SubscriptionDevMode
                          apiUrl={config.subscriptions?.api_url || ""}
                          onSave={() => {
                            // Refresh list after save if needed
                          }}
                        />
                      ) : (
                        <SubscriptionList
                          apiUrl={config.subscriptions?.api_url || ""}
                        />
                      )}
                    </div>
                  </div>
                )}

                {activeTab === "card_reader" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-credit-card me-2"></i>
                      Cấu hình Đọc thẻ từ
                    </h6>
                    <div className="alert alert-info">
                      <i className="bi bi-info-circle me-2"></i>
                      Cấu hình đọc thẻ từ sẽ được thêm vào sau
                    </div>
                  </div>
                )}

                {activeTab === "report" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-file-earmark-text me-2"></i>
                      Cấu hình Gửi báo cáo
                    </h6>
                    <div className="mb-3">
                      <label className="form-label small">
                        API Endpoint gửi báo cáo
                      </label>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        value={config.report?.api_url || ""}
                        onChange={(e) =>
                          updateConfig("report", "api_url", e.target.value)
                        }
                        placeholder="https://api.example.com/reports"
                      />
                      <small className="text-muted">
                        <i className="bi bi-info-circle me-1"></i>
                        Nhập URL API endpoint để hệ thống gửi báo cáo tự động
                      </small>
                    </div>
                  </div>
                )}

                {activeTab === "central_server" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-server me-2"></i>
                      Cấu hình IP máy chủ central
                    </h6>
                    <div className="mb-3">
                      <label className="form-label small">
                        IP/URL máy chủ central
                      </label>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        value={config.central_server?.ip || ""}
                        onChange={(e) =>
                          updateConfig("central_server", "ip", e.target.value)
                        }
                        placeholder="http://192.168.1.100:8000"
                      />
                      <small className="text-muted">
                        <i className="bi bi-info-circle me-1"></i>
                        Nhập IP/URL của máy chủ central hiện tại
                      </small>
                    </div>
                  </div>
                )}

                {activeTab === "central_sync" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-arrow-repeat me-2"></i>
                      Cấu hình IP máy chủ central khác (Đồng bộ dữ liệu)
                    </h6>
                    <div className="mb-3">
                      <label className="form-label small">
                        Danh sách IP/URL máy chủ central khác
                      </label>
                      <CentralSyncServersList
                        config={config}
                        updateConfig={updateConfig}
                      />
                      <small className="text-muted">
                        <i className="bi bi-info-circle me-1"></i>
                        Nhập danh sách IP/URL các máy chủ central khác để đồng
                        bộ dữ liệu
                      </small>
                    </div>
                  </div>
                )}

                {activeTab === "central_server" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-server me-2"></i>
                      Cấu hình IP máy chủ central
                    </h6>
                    <div className="mb-3">
                      <label className="form-label small">
                        IP/URL máy chủ central
                      </label>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        value={config.central_server?.ip || ""}
                        onChange={(e) =>
                          updateConfig("central_server", "ip", e.target.value)
                        }
                        placeholder="http://192.168.1.100:8000"
                      />
                      <small className="text-muted">
                        <i className="bi bi-info-circle me-1"></i>
                        Nhập IP/URL của máy chủ central hiện tại
                      </small>
                    </div>
                  </div>
                )}

                {activeTab === "central_sync" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-arrow-repeat me-2"></i>
                      Cấu hình IP máy chủ central khác (Đồng bộ dữ liệu)
                    </h6>
                    <div className="mb-3">
                      <label className="form-label small">
                        Danh sách IP/URL máy chủ central khác
                      </label>
                      <CentralSyncServersList
                        config={config}
                        updateConfig={updateConfig}
                      />
                      <small className="text-muted">
                        <i className="bi bi-info-circle me-1"></i>
                        Nhập danh sách IP/URL các máy chủ central khác để đồng
                        bộ dữ liệu
                      </small>
                    </div>
                  </div>
                )}

                {activeTab === "barrier" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-radioactive me-2"></i>
                      Cấu hình Barrier hồng ngoại
                    </h6>
                    <div className="alert alert-info">
                      <i className="bi bi-info-circle me-2"></i>
                      Cấu hình barrier hồng ngoại sẽ được thêm vào sau
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="alert alert-danger">Không thể tải cấu hình</div>
            )}
          </div>
          <div className="modal-footer">
            <button className="btn btn-secondary btn-sm" onClick={onClose}>
              Đóng
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleSave}
              disabled={saving || !config}
            >
              {saving ? (
                <>
                  <span className="spinner-border spinner-border-sm me-2"></span>
                  Đang lưu...
                </>
              ) : (
                <>
                  <i className="bi bi-save me-2"></i>
                  Lưu cấu hình
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

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
    // Fetch stats (vẫn dùng polling vì không thay đổi thường xuyên)
    fetchStats();
    const statsInterval = setInterval(fetchStats, 10000);

    // WebSocket cho camera updates (real-time)
    const wsUrl = CENTRAL_URL.replace("http", "ws") + "/ws/cameras";
    let ws = null;
    let reconnectTimer = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("[Cameras] WebSocket connected");
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
          // Reconnect sau 3 giây
          reconnectTimer = setTimeout(connect, 3000);
        };

        // Send ping every 10 seconds to keep connection alive
        let pingInterval = null;
        if (ws && ws.readyState === WebSocket.OPEN) {
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

          // Cleanup ping interval when connection closes
          const originalOnClose = ws.onclose;
          ws.onclose = (event) => {
            if (pingInterval) clearInterval(pingInterval);
            if (originalOnClose) originalOnClose.call(ws, event);
          };
        }
      } catch (err) {
        console.error("[Cameras] WebSocket connection error:", err);
        reconnectTimer = setTimeout(connect, 3000);
      }
    };

    connect();

    return () => {
      if (statsInterval) clearInterval(statsInterval);
      if (reconnectTimer) clearTimeout(reconnectTimer);
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
