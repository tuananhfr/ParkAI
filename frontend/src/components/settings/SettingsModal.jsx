import { useState, useEffect } from "react";
import { CENTRAL_URL } from "@/config";
import useBackendType from "@/hooks/useBackendType";
import SubscriptionDevMode from "./subscription/SubscriptionDevMode";
import SubscriptionList from "./subscription/SubscriptionList";
import StaffList from "./staff/StaffList";
import P2PSettings from "./p2p/P2PSettings";

/**
 * SettingsModal - Component modal cài đặt hệ thống
 */
const SettingsModal = ({ show, onClose, onSaveSuccess }) => {
  const { backendType, isEdge, isCentral } = useBackendType();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [activeTab, setActiveTab] = useState("cameras");
  const [showAddCameraForm, setShowAddCameraForm] = useState(false);
  const [subscriptionDevMode, setSubscriptionDevMode] = useState(false);
  const [newCamera, setNewCamera] = useState({
    name: "",
    ip: "",
    camera_type: "ENTRY",
  });
  const [frontendBackendHost, setFrontendBackendHost] = useState("");
  const [frontendBackendPort, setFrontendBackendPort] = useState("");

  useEffect(() => {
    if (show) {
      fetchConfig();
      setActiveTab("cameras");
      setShowAddCameraForm(false);
      setNewCamera({
        name: "",
        ip: "",
        camera_type: "ENTRY",
      });
      setMessage(null);

      //Parse CENTRAL_URL de fill host/port cho tab Frontend → Backend
      try {
        const url = new URL(CENTRAL_URL);
        setFrontendBackendHost(url.hostname || "");
        setFrontendBackendPort(
          url.port || (url.protocol === "https:" ? "443" : "80")
        );
      } catch (e) {
        setFrontendBackendHost("");
        setFrontendBackendPort("");
      }
    }
  }, [show]);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${CENTRAL_URL}/api/config`);
      const data = await response.json();
      console.log("[Settings] Fetched config:", data);
      console.log("[Settings] Parking lot capacity from backend:", data.config?.parking_lot?.capacity);
      if (data.success) {
        setConfig(data.config);
      }
    } catch (err) {
      console.error("[Settings] Fetch error:", err);
      setMessage({ type: "error", text: "Không thể tải cấu hình" });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      console.log("[Settings] Saving config:", config);
      console.log("[Settings] Parking lot capacity:", config.parking_lot?.capacity);

      const response = await fetch(`${CENTRAL_URL}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await response.json();

      console.log("[Settings] Save response:", data);

      if (data.success) {
        console.log("[Settings] Config saved successfully");
        console.log("[Settings] Returned config:", data.config);

        // Broadcast config change event to all components
        window.dispatchEvent(new CustomEvent('configUpdated', {
          detail: { timestamp: Date.now() }
        }));

        onClose();
        if (typeof onSaveSuccess === "function") {
          onSaveSuccess();
        }
      } else {
        setMessage({
          type: "error",
          text: `${data.error || "Lỗi lưu cấu hình"}`,
        });
      }
    } catch (err) {
      console.error("[Settings] Save error:", err);
      setMessage({ type: "error", text: "Không thể lưu cấu hình" });
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
        ...(prev.edge_cameras || {}),
        [camId]: {
          ...(prev.edge_cameras?.[camId] || {}),
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

    const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipPattern.test(newCamera.ip.trim())) {
      setMessage({
        type: "error",
        text: "IP address không hợp lệ. Vui lòng nhập đúng định dạng (ví dụ: 192.168.0.144)",
      });
      return;
    }

    const existingIds = Object.keys(config.edge_cameras || {})
      .map((id) => parseInt(id, 10))
      .filter((id) => !isNaN(id));
    const maxId = existingIds.length > 0 ? Math.max(...existingIds) : 0;
    const newCameraId = maxId + 1;

    setConfig((prev) => ({
      ...prev,
      edge_cameras: {
        ...(prev.edge_cameras || {}),
        [newCameraId]: {
          name: newCamera.name.trim(),
          ip: newCamera.ip.trim(),
          camera_type: newCamera.camera_type || "ENTRY",
        },
      },
    }));

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
          config.edge_cameras?.[camId]?.name || ""
        }?`
      )
    ) {
      setConfig((prev) => {
        const newCameras = { ...(prev.edge_cameras || {}) };
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
            {loading || !backendType ? (
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
                        activeTab === "barrier" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("barrier")}
                      type="button"
                    >
                      <i className="bi bi-door-closed me-2"></i>
                      Barrier
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
                        activeTab === "frontend_backend" ? "active" : ""
                      }`}
                      onClick={() => setActiveTab("frontend_backend")}
                      type="button"
                    >
                      <i className="bi bi-plug me-2"></i>
                      Kết nối Frontend → Backend
                    </button>
                  </li>
                  {backendType !== "edge" && (
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
                  )}
                </ul>

                {/* Tab Content */}
                {activeTab === "parking" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-cash-coin me-2"></i>
                      Phí gửi xe
                    </h6>
                    <div className="mb-3">
                      <label className="form-label small">
                        API Endpoint phí gửi xe (để trống sẽ dùng file JSON)
                      </label>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        value={config.parking?.api_url || ""}
                        onChange={(e) =>
                          updateConfig("parking", "api_url", e.target.value)
                        }
                        placeholder="https://api.example.com/parking/fees"
                      />
                      <small className="text-muted">
                        <i className="bi bi-info-circle me-1"></i>
                        Nếu để trống, hệ thống sẽ dùng dữ liệu trong file
                        `data/parking_fees.json`
                      </small>
                    </div>
                    <div className="row g-3 mb-4">
                      <div className="col-md-6">
                        <label className="form-label small">
                          Số giờ miễn phí
                        </label>
                        <div className="input-group input-group-sm">
                          <input
                            type="number"
                            className="form-control"
                            value={config.parking.fee_base}
                            min="0"
                            step="0.1"
                            onChange={(e) =>
                              updateConfig(
                                "parking",
                                "fee_base",
                                parseFloat(e.target.value || "0")
                              )
                            }
                          />
                          <span className="input-group-text">giờ</span>
                        </div>
                        <small className="text-muted">
                          Ví dụ: 0.5 giờ = 30 phút miễn phí
                        </small>
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
                    </div>
                  </div>
                )}

                {activeTab === "cameras" && (
                  <div>
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
                        value={config.camera?.heartbeat_timeout || 30}
                        onChange={(e) =>
                          updateConfig(
                            "camera",
                            "heartbeat_timeout",
                            parseInt(e.target.value)
                          )
                        }
                      />
                    </div>

                    <div className="d-flex justify-content-between align-items-center mb-3">
                      <h6 className="border-bottom pb-2 mb-0">
                        <i className="bi bi-hdd-network me-2"></i>
                        Edge Cameras
                        {backendType === "edge" && (
                          <span className="badge bg-info ms-2">
                            Single Camera Mode
                          </span>
                        )}
                      </h6>
                      {backendType !== "edge" && (
                        <button
                          className="btn btn-sm btn-primary"
                          onClick={() =>
                            setShowAddCameraForm(!showAddCameraForm)
                          }
                        >
                          <i className="bi bi-plus-circle me-1"></i>
                          Thêm camera
                        </button>
                      )}
                    </div>

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
                                <option value="PARKING_LOT">TRONG BÃI</option>
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

                    {Object.entries(config.edge_cameras || {})
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
                                      : camConfig.camera_type === "EXIT"
                                      ? "bg-danger"
                                      : "bg-secondary"
                                  } ms-2`}
                                >
                                  {camConfig.camera_type === "ENTRY"
                                    ? "VÀO"
                                    : camConfig.camera_type === "EXIT"
                                    ? "RA"
                                    : "TRONG BÃI"}
                                </span>
                              </h6>
                              {backendType !== "edge" && (
                                <button
                                  className="btn btn-sm btn-outline-danger"
                                  onClick={() => handleRemoveCamera(camId)}
                                  title="Xóa camera"
                                >
                                  <i className="bi bi-trash"></i>
                                </button>
                              )}
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
                                  {backendType === "edge" && (
                                    <span className="badge bg-secondary ms-2">
                                      auto
                                    </span>
                                  )}
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
                                  disabled={backendType === "edge"}
                                  readOnly={backendType === "edge"}
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
                                  <option value="PARKING_LOT">TRONG BÃI</option>
                                </select>
                              </div>
                            </div>

                            {/* Capacity input - chỉ hiển thị khi camera type = PARKING_LOT */}
                            {camConfig.camera_type === "PARKING_LOT" && (
                              <div className="row g-2 mt-2">
                                <div className="col-md-12">
                                  <label className="form-label small">
                                    <i className="bi bi-car-front me-1"></i>
                                    Tổng số chỗ đỗ xe
                                  </label>
                                  <input
                                    type="text"
                                    className="form-control form-control-sm"
                                    value={
                                      config.parking_lot?.capacity > 0
                                        ? config.parking_lot.capacity
                                        : ""
                                    }
                                    onChange={(e) => {
                                      const value = e.target.value;
                                      // Chỉ cho phép số hoặc rỗng
                                      if (value === "" || /^\d+$/.test(value)) {
                                        const numValue = value === "" ? 0 : parseInt(value, 10);
                                        console.log("[Settings] Updating capacity:", numValue);
                                        updateConfig(
                                          "parking_lot",
                                          "capacity",
                                          numValue
                                        );
                                      }
                                    }}
                                    placeholder="Ví dụ: 10"
                                  />
                                  <small className="text-muted">
                                    <i className="bi bi-info-circle me-1"></i>
                                    Số lượng chỗ đỗ xe mà camera này quản lý
                                  </small>
                                </div>
                              </div>
                            )}

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
                          onSave={() => {}}
                        />
                      ) : (
                        <SubscriptionList
                          apiUrl={config.subscriptions?.api_url || ""}
                        />
                      )}
                    </div>
                  </div>
                )}

                {activeTab === "barrier" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-door-closed me-2"></i>
                      Cài đặt Barrier
                    </h6>

                    <div className="alert alert-info mb-3">
                      <strong>Lưu ý:</strong> Đây là cài đặt <strong>CÓ/KHÔNG</strong> sử dụng hệ thống barrier.
                      <br />
                      Sau khi bật, bạn sẽ có nút <strong>MỞ/ĐÓNG</strong> barrier trên frontend.
                    </div>

                    <div className="mb-3">
                      <div className="form-check form-switch">
                        <input
                          className="form-check-input"
                          type="checkbox"
                          id="barrierEnabled"
                          checked={config.barrier?.enabled || false}
                          onChange={(e) =>
                            updateConfig("barrier", "enabled", e.target.checked)
                          }
                        />
                        <label className="form-check-label" htmlFor="barrierEnabled">
                          <strong>CÓ sử dụng hệ thống Barrier</strong>
                        </label>
                      </div>
                      <small className="text-muted d-block mt-2">
                        <i className="bi bi-info-circle me-1"></i>
                        <strong>BẬT:</strong> Hệ thống có barrier → Nhập biển → Mở barrier → Đợi đóng → Lưu DB
                        <br />
                        <strong>TẮT:</strong> Không có barrier → Nhập biển → Lưu DB ngay
                      </small>
                    </div>
                    {config.barrier?.enabled && (
                      <div className="card border-primary">
                        <div className="card-body">
                          <h6 className="card-title text-primary mb-3">
                            <i className="bi bi-gear me-2"></i>
                            Cấu hình GPIO
                          </h6>
                          <div className="row g-3">
                            <div className="col-md-6">
                              <label className="form-label small">
                                GPIO Pin
                              </label>
                              <input
                                type="number"
                                className="form-control form-control-sm"
                                value={config.barrier?.gpio_pin || 18}
                                onChange={(e) =>
                                  updateConfig(
                                    "barrier",
                                    "gpio_pin",
                                    parseInt(e.target.value)
                                  )
                                }
                              />
                              <small className="text-muted">
                                GPIO pin để điều khiển relay barrier
                              </small>
                            </div>
                            <div className="col-md-6">
                              <label className="form-label small">
                                Tự động đóng sau (giây)
                              </label>
                              <input
                                type="number"
                                className="form-control form-control-sm"
                                value={config.barrier?.auto_close_time || 5.0}
                                step="0.5"
                                onChange={(e) =>
                                  updateConfig(
                                    "barrier",
                                    "auto_close_time",
                                    parseFloat(e.target.value)
                                  )
                                }
                              />
                              <small className="text-muted">
                                Để 0 nếu không muốn tự động đóng
                              </small>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
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
                      {backendType === "edge"
                        ? "Kết nối đến Central Server"
                        : "Cấu hình máy chủ Central hiện tại"}
                    </h6>

                    <div className="mb-3">
                      <label className="form-label small">
                        {backendType === "edge"
                          ? "IP/URL Central Server (để trống nếu standalone)"
                          : "IP máy chủ Central này"}
                        {backendType === "central" && (
                          <span className="badge bg-secondary ms-2">auto</span>
                        )}
                      </label>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        value={config.central_server?.ip || ""}
                        onChange={(e) =>
                          updateConfig("central_server", "ip", e.target.value)
                        }
                        placeholder={
                          backendType === "edge"
                            ? "http://192.168.1.100:8000 (hoac de trong)"
                            : "auto hoặc 192.168.1.100"
                        }
                        disabled={backendType === "central"}
                        readOnly={backendType === "central"}
                      />
                      <small className="text-muted">
                        <i className="bi bi-info-circle me-1"></i>
                        {backendType === "edge"
                          ? "Nhập IP/URL của Central Server hoặc để trống để sử dụng Edge standalone"
                          : "IP này được tự động phát hiện khi khởi động Central Server"}
                      </small>
                    </div>
                  </div>
                )}

                {activeTab === "frontend_backend" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-plug me-2"></i>
                      Kết nối Frontend → Backend
                    </h6>

                    {(() => {
                      try {
                        const url = new URL(CENTRAL_URL);
                        const host = frontendBackendHost || url.hostname || "";
                        const port =
                          frontendBackendPort ||
                          url.port ||
                          (url.protocol === "https:" ? "443" : "80");
                        return (
                          <div className="row g-3">
                            <div className="col-md-6">
                              <label className="form-label small">
                                IP / Host
                              </label>
                              <input
                                type="text"
                                className="form-control form-control-sm"
                                value={host}
                                onChange={(e) =>
                                  setFrontendBackendHost(e.target.value)
                                }
                              />
                            </div>
                            <div className="col-md-6">
                              <label className="form-label small">Port</label>
                              <input
                                type="text"
                                className="form-control form-control-sm"
                                value={port}
                                onChange={(e) =>
                                  setFrontendBackendPort(e.target.value)
                                }
                              />
                            </div>
                          </div>
                        );
                      } catch (e) {
                        return (
                          <div className="alert alert-warning">
                            <i className="bi bi-exclamation-triangle me-2"></i>
                            CENTRAL_URL không phải URL hợp lệ. Giá trị hiện tại:{" "}
                            <code>{CENTRAL_URL}</code>
                          </div>
                        );
                      }
                    })()}

                    <div className="mt-3 d-flex justify-content-between align-items-center">
                      <button
                        type="button"
                        className="btn btn-outline-secondary btn-sm"
                        onClick={() => {
                          if (
                            window.confirm("Reset về CENTRAL_URL mặc định?")
                          ) {
                            window.localStorage.removeItem(
                              "central_url_override"
                            );
                            window.location.reload();
                          }
                        }}
                      >
                        Reset về mặc định
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => {
                          try {
                            const baseUrl = new URL(CENTRAL_URL);
                            const host = frontendBackendHost.trim();
                            const port = frontendBackendPort.trim();
                            if (!host) {
                              alert("Vui lòng nhập IP/Host backend");
                              return;
                            }
                            const protocol = baseUrl.protocol || "http:";
                            const newUrl = `${protocol}//${host}${
                              port ? `:${port}` : ""
                            }`;
                            window.localStorage.setItem(
                              "central_url_override",
                              newUrl
                            );
                            if (
                              window.confirm(
                                `Đã lưu backend: ${newUrl}. Reload trang để áp dụng ngay?`
                              )
                            ) {
                              window.location.reload();
                            }
                          } catch (e) {
                            alert(
                              "CENTRAL_URL hiện tại không hợp lệ, không thể build URL mới."
                            );
                          }
                        }}
                      >
                        Lưu IP/Port & Reload
                      </button>
                    </div>
                  </div>
                )}

                {activeTab === "central_sync" && (
                  <div>
                    <h6 className="border-bottom pb-2 mb-3">
                      <i className="bi bi-arrow-repeat me-2"></i>
                      Cấu hình P2P Đồng bộ dữ liệu
                    </h6>
                    <P2PSettings />
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

export default SettingsModal;
