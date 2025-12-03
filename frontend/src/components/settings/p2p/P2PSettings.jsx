import { useState, useEffect } from "react";
import { CENTRAL_URL } from "@/config";

/**
 * P2PSettings - Component quản lý cấu hình P2P đồng bộ giữa các Central servers
 *
 * Features:
 * - Hiển thị cấu hình Central hiện tại (ID, IP, Port)
 * - Quản lý danh sách Peer Centrals
 * - Hiển thị trạng thái kết nối P2P real-time
 * - Sync state monitoring
 */
const P2PSettings = () => {
  const [p2pConfig, setP2pConfig] = useState(null);
  const [p2pStatus, setP2pStatus] = useState(null);
  const [syncState, setSyncState] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [showAddPeer, setShowAddPeer] = useState(false);
  const [newPeer, setNewPeer] = useState({
    id: "",
    ip: "",
    p2p_port: 9000,
  });

  // Fetch P2P configuration
  const fetchP2PConfig = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/p2p/config`);
      const data = await response.json();
      if (data.success) {
        setP2pConfig(data.config);
      }
    } catch (err) {
      console.error("Lỗi khi tải cấu hình P2P:", err);
    }
  };

  // Fetch P2P status
  const fetchP2PStatus = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/p2p/status`);
      const data = await response.json();
      if (data.success) {
        setP2pStatus(data);
      }
    } catch (err) {
      console.error("Lỗi khi tải trạng thái P2P:", err);
    }
  };

  // Fetch sync state
  const fetchSyncState = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/p2p/sync-state`);
      const data = await response.json();
      if (data.success) {
        setSyncState(data.sync_state || []);
      }
    } catch (err) {
      console.error("Lỗi khi tải trạng thái sync:", err);
    }
  };

  // Initial load
  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      await Promise.all([
        fetchP2PConfig(),
        fetchP2PStatus(),
        fetchSyncState(),
      ]);
      setLoading(false);
    };
    loadAll();

    // Auto refresh status every 10s
    const interval = setInterval(() => {
      fetchP2PStatus();
      fetchSyncState();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  // Save P2P configuration
  const handleSaveConfig = async () => {
    try {
      setSaving(true);
      setMessage(null);

      const response = await fetch(`${CENTRAL_URL}/api/p2p/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(p2pConfig),
      });

      const data = await response.json();
      if (data.success) {
        setMessage({
          type: "success",
          text: "✅ Đã lưu cấu hình P2P. Vui lòng khởi động lại server để áp dụng.",
        });
        await fetchP2PConfig();
      } else {
        setMessage({
          type: "error",
          text: `❌ ${data.error || "Lỗi khi lưu cấu hình"}`,
        });
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: "❌ Không thể lưu cấu hình P2P",
      });
    } finally {
      setSaving(false);
    }
  };

  // Update this central config
  const updateThisCentral = (key, value) => {
    setP2pConfig((prev) => ({
      ...prev,
      this_central: {
        ...prev.this_central,
        [key]: value,
      },
    }));
  };

  // Add peer central
  const handleAddPeer = () => {
    if (!newPeer.id.trim() || !newPeer.ip.trim()) {
      setMessage({
        type: "error",
        text: "❌ Vui lòng điền đầy đủ ID và IP address",
      });
      return;
    }

    // Check duplicate ID
    const exists = p2pConfig.peer_centrals.some(
      (peer) => peer.id === newPeer.id.trim()
    );
    if (exists) {
      setMessage({
        type: "error",
        text: `❌ Central ID "${newPeer.id.trim()}" đã tồn tại`,
      });
      return;
    }

    // Add peer
    setP2pConfig((prev) => ({
      ...prev,
      peer_centrals: [
        ...prev.peer_centrals,
        {
          id: newPeer.id.trim(),
          ip: newPeer.ip.trim(),
          p2p_port: newPeer.p2p_port,
        },
      ],
    }));

    setNewPeer({ id: "", ip: "", p2p_port: 9000 });
    setShowAddPeer(false);
    setMessage({
      type: "success",
      text: `✅ Đã thêm peer "${newPeer.id.trim()}". Nhớ lưu cấu hình!`,
    });
  };

  // Remove peer central
  const handleRemovePeer = (peerId) => {
    if (window.confirm(`Bạn có chắc muốn xóa peer "${peerId}"?`)) {
      setP2pConfig((prev) => ({
        ...prev,
        peer_centrals: prev.peer_centrals.filter((peer) => peer.id !== peerId),
      }));
      setMessage({
        type: "success",
        text: `✅ Đã xóa peer "${peerId}". Nhớ lưu cấu hình!`,
      });
    }
  };

  // Update peer central
  const updatePeer = (peerId, key, value) => {
    setP2pConfig((prev) => ({
      ...prev,
      peer_centrals: prev.peer_centrals.map((peer) =>
        peer.id === peerId ? { ...peer, [key]: value } : peer
      ),
    }));
  };

  // Test connection to peer
  const handleTestConnection = async (peerId) => {
    try {
      setMessage({
        type: "info",
        text: `🔄 Đang kiểm tra kết nối đến "${peerId}"...`,
      });

      const response = await fetch(
        `${CENTRAL_URL}/api/p2p/test-connection?peer_id=${peerId}`,
        { method: "POST" }
      );

      const data = await response.json();
      if (data.success) {
        setMessage({
          type: "success",
          text: `✅ Kết nối thành công đến "${peerId}"`,
        });
      } else {
        setMessage({
          type: "error",
          text: `❌ Không thể kết nối đến "${peerId}": ${data.error}`,
        });
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: `❌ Lỗi khi kiểm tra kết nối: ${err.message}`,
      });
    }
  };

  // Get peer connection status
  const getPeerStatus = (peerId) => {
    if (!p2pStatus || !p2pStatus.peers) return "unknown";
    const peer = p2pStatus.peers.find((p) => p.peer_id === peerId);
    return peer ? peer.status : "unknown";
  };

  // Get last sync info
  const getSyncInfo = (peerId) => {
    const sync = syncState.find((s) => s.peer_central_id === peerId);
    return sync;
  };

  // Format timestamp
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return "Chưa đồng bộ";
    const date = new Date(timestamp);
    return date.toLocaleString("vi-VN");
  };

  if (loading) {
    return (
      <div className="text-center py-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Đang tải...</span>
        </div>
        <p className="mt-2 text-muted">Đang tải cấu hình P2P...</p>
      </div>
    );
  }

  if (!p2pConfig) {
    return (
      <div className="alert alert-danger">
        <i className="bi bi-exclamation-triangle me-2"></i>
        Không thể tải cấu hình P2P. Vui lòng kiểm tra backend server.
      </div>
    );
  }

  return (
    <div>
      {/* Message */}
      {message && (
        <div
          className={`alert alert-${
            message.type === "success"
              ? "success"
              : message.type === "info"
              ? "info"
              : "danger"
          } alert-dismissible fade show`}
          role="alert"
        >
          {message.text}
          <button
            type="button"
            className="btn-close"
            onClick={() => setMessage(null)}
          ></button>
        </div>
      )}

      {/* P2P Status Overview */}
      <div className="card mb-4 border-primary">
        <div className="card-header bg-primary text-white">
          <h6 className="mb-0">
            <i className="bi bi-broadcast me-2"></i>
            Trạng thái P2P Network
          </h6>
        </div>
        <div className="card-body">
          {p2pStatus ? (
            <div className="row g-3">
              <div className="col-md-3">
                <div className="text-center">
                  <h4 className="mb-0">
                    <span
                      className={`badge ${
                        p2pStatus.running ? "bg-success" : "bg-danger"
                      }`}
                    >
                      {p2pStatus.running ? "Đang chạy" : "Dừng"}
                    </span>
                  </h4>
                  <small className="text-muted">Trạng thái P2P</small>
                </div>
              </div>
              <div className="col-md-3">
                <div className="text-center">
                  <h4 className="mb-0 text-primary">
                    {p2pStatus.connected_peers || 0}
                  </h4>
                  <small className="text-muted">Peers kết nối</small>
                </div>
              </div>
              <div className="col-md-3">
                <div className="text-center">
                  <h4 className="mb-0 text-info">
                    {p2pStatus.total_peers || 0}
                  </h4>
                  <small className="text-muted">Tổng số peers</small>
                </div>
              </div>
              <div className="col-md-3">
                <div className="text-center">
                  <h4 className="mb-0 text-secondary">
                    {p2pConfig.this_central?.id || "N/A"}
                  </h4>
                  <small className="text-muted">Central ID</small>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center text-muted">
              Không có thông tin trạng thái
            </div>
          )}
        </div>
      </div>

      {/* This Central Configuration */}
      <div className="card mb-4">
        <div className="card-header bg-secondary text-white">
          <h6 className="mb-0">
            <i className="bi bi-server me-2"></i>
            Cấu hình Central hiện tại
          </h6>
        </div>
        <div className="card-body">
          <div className="row g-3">
            <div className="col-md-4">
              <label className="form-label small">
                Central ID <span className="text-danger">*</span>
              </label>
              <input
                type="text"
                className="form-control form-control-sm"
                value={p2pConfig.this_central?.id || ""}
                onChange={(e) => updateThisCentral("id", e.target.value)}
                placeholder="central-1"
              />
              <small className="text-muted">
                ID duy nhất của central này (ví dụ: central-1, central-2)
              </small>
            </div>
            <div className="col-md-4">
              <label className="form-label small">
                IP Address <span className="text-danger">*</span>
              </label>
              <input
                type="text"
                className="form-control form-control-sm"
                value={p2pConfig.this_central?.ip || ""}
                onChange={(e) => updateThisCentral("ip", e.target.value)}
                placeholder="192.168.1.101"
              />
              <small className="text-muted">
                IP của máy chủ central này trong mạng LAN
              </small>
            </div>
            <div className="col-md-2">
              <label className="form-label small">P2P Port</label>
              <input
                type="number"
                className="form-control form-control-sm"
                value={p2pConfig.this_central?.p2p_port || 9000}
                onChange={(e) =>
                  updateThisCentral("p2p_port", parseInt(e.target.value))
                }
              />
              <small className="text-muted">Port WebSocket P2P</small>
            </div>
            <div className="col-md-2">
              <label className="form-label small">API Port</label>
              <input
                type="number"
                className="form-control form-control-sm"
                value={p2pConfig.this_central?.api_port || 8000}
                onChange={(e) =>
                  updateThisCentral("api_port", parseInt(e.target.value))
                }
              />
              <small className="text-muted">Port HTTP API</small>
            </div>
          </div>
        </div>
      </div>

      {/* Peer Centrals List */}
      <div className="card mb-4">
        <div className="card-header bg-info text-white d-flex justify-content-between align-items-center">
          <h6 className="mb-0">
            <i className="bi bi-diagram-3 me-2"></i>
            Danh sách Peer Centrals ({p2pConfig.peer_centrals?.length || 0})
          </h6>
          <button
            className="btn btn-sm btn-light"
            onClick={() => setShowAddPeer(!showAddPeer)}
          >
            <i className="bi bi-plus-circle me-1"></i>
            Thêm Peer
          </button>
        </div>
        <div className="card-body">
          {/* Add Peer Form */}
          {showAddPeer && (
            <div className="card mb-3 border-success">
              <div className="card-body">
                <h6 className="card-title text-success">
                  <i className="bi bi-plus-circle me-2"></i>
                  Thêm Peer Central mới
                </h6>
                <div className="row g-2">
                  <div className="col-md-4">
                    <label className="form-label small">
                      Peer ID <span className="text-danger">*</span>
                    </label>
                    <input
                      type="text"
                      className="form-control form-control-sm"
                      value={newPeer.id}
                      onChange={(e) =>
                        setNewPeer({ ...newPeer, id: e.target.value })
                      }
                      placeholder="central-2"
                    />
                  </div>
                  <div className="col-md-5">
                    <label className="form-label small">
                      IP Address <span className="text-danger">*</span>
                    </label>
                    <input
                      type="text"
                      className="form-control form-control-sm"
                      value={newPeer.ip}
                      onChange={(e) =>
                        setNewPeer({ ...newPeer, ip: e.target.value })
                      }
                      placeholder="192.168.1.102"
                    />
                  </div>
                  <div className="col-md-3">
                    <label className="form-label small">P2P Port</label>
                    <input
                      type="number"
                      className="form-control form-control-sm"
                      value={newPeer.p2p_port}
                      onChange={(e) =>
                        setNewPeer({
                          ...newPeer,
                          p2p_port: parseInt(e.target.value),
                        })
                      }
                    />
                  </div>
                </div>
                <div className="mt-2 d-flex gap-2">
                  <button
                    className="btn btn-sm btn-success"
                    onClick={handleAddPeer}
                  >
                    <i className="bi bi-check-circle me-1"></i>
                    Thêm
                  </button>
                  <button
                    className="btn btn-sm btn-secondary"
                    onClick={() => {
                      setShowAddPeer(false);
                      setNewPeer({ id: "", ip: "", p2p_port: 9000 });
                    }}
                  >
                    <i className="bi bi-x-circle me-1"></i>
                    Hủy
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Peer List */}
          {p2pConfig.peer_centrals?.length === 0 ? (
            <div className="alert alert-warning">
              <i className="bi bi-info-circle me-2"></i>
              Chưa có peer central nào. Thêm peer để bật P2P sync.
              <br />
              <small className="text-muted">
                Nếu không có peer, central sẽ hoạt động ở chế độ standalone.
              </small>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="table table-sm table-hover">
                <thead className="table-light">
                  <tr>
                    <th style={{ width: "20%" }}>Peer ID</th>
                    <th style={{ width: "25%" }}>IP Address</th>
                    <th style={{ width: "10%" }}>Port</th>
                    <th style={{ width: "15%" }}>Trạng thái</th>
                    <th style={{ width: "20%" }}>Sync lần cuối</th>
                    <th style={{ width: "10%" }} className="text-end">
                      Thao tác
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {p2pConfig.peer_centrals.map((peer) => {
                    const status = getPeerStatus(peer.id);
                    const syncInfo = getSyncInfo(peer.id);

                    return (
                      <tr key={peer.id}>
                        <td>
                          <strong>{peer.id}</strong>
                        </td>
                        <td>
                          <input
                            type="text"
                            className="form-control form-control-sm"
                            value={peer.ip}
                            onChange={(e) =>
                              updatePeer(peer.id, "ip", e.target.value)
                            }
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            className="form-control form-control-sm"
                            value={peer.p2p_port}
                            onChange={(e) =>
                              updatePeer(
                                peer.id,
                                "p2p_port",
                                parseInt(e.target.value)
                              )
                            }
                          />
                        </td>
                        <td>
                          {status === "connected" && (
                            <span className="badge bg-success">
                              <i className="bi bi-check-circle me-1"></i>
                              Kết nối
                            </span>
                          )}
                          {status === "disconnected" && (
                            <span className="badge bg-danger">
                              <i className="bi bi-x-circle me-1"></i>
                              Mất kết nối
                            </span>
                          )}
                          {status === "connecting" && (
                            <span className="badge bg-warning">
                              <i className="bi bi-arrow-repeat me-1"></i>
                              Đang kết nối
                            </span>
                          )}
                          {status === "unknown" && (
                            <span className="badge bg-secondary">
                              <i className="bi bi-question-circle me-1"></i>
                              Không rõ
                            </span>
                          )}
                        </td>
                        <td>
                          <small>
                            {syncInfo ? (
                              <>
                                <div>{syncInfo.last_sync_time}</div>
                                <div className="text-muted">
                                  {formatTimestamp(
                                    syncInfo.last_sync_timestamp
                                  )}
                                </div>
                              </>
                            ) : (
                              <span className="text-muted">Chưa đồng bộ</span>
                            )}
                          </small>
                        </td>
                        <td className="text-end">
                          <div className="btn-group btn-group-sm">
                            <button
                              className="btn btn-outline-primary"
                              onClick={() => handleTestConnection(peer.id)}
                              title="Kiểm tra kết nối"
                            >
                              <i className="bi bi-lightning"></i>
                            </button>
                            <button
                              className="btn btn-outline-danger"
                              onClick={() => handleRemovePeer(peer.id)}
                              title="Xóa peer"
                            >
                              <i className="bi bi-trash"></i>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Save Button */}
      <div className="d-flex justify-content-end gap-2">
        <button
          className="btn btn-primary"
          onClick={handleSaveConfig}
          disabled={saving}
        >
          {saving ? (
            <>
              <span className="spinner-border spinner-border-sm me-2"></span>
              Đang lưu...
            </>
          ) : (
            <>
              <i className="bi bi-save me-2"></i>
              Lưu cấu hình P2P
            </>
          )}
        </button>
      </div>

      {/* Info Footer */}
      <div className="alert alert-info mt-4">
        <h6 className="alert-heading">
          <i className="bi bi-info-circle me-2"></i>
          Hướng dẫn cấu hình P2P
        </h6>
        <ul className="mb-0 small">
          <li>
            <strong>Central ID:</strong> Phải duy nhất cho mỗi central (ví dụ:
            central-1, central-2, ...)
          </li>
          <li>
            <strong>IP Address:</strong> IP của central trong mạng LAN (ví dụ:
            192.168.1.101)
          </li>
          <li>
            <strong>P2P Port:</strong> Port cho WebSocket P2P (mặc định: 9000)
          </li>
          <li>
            <strong>Peer Centrals:</strong> Danh sách các central khác để đồng
            bộ dữ liệu
          </li>
          <li>
            <strong>Lưu ý:</strong> Sau khi lưu cấu hình, cần khởi động lại
            server để áp dụng
          </li>
        </ul>
      </div>
    </div>
  );
};

export default P2PSettings;
