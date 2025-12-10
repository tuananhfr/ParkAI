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
  const [message, setMessage] = useState(null);
  const [showAddPeer, setShowAddPeer] = useState(false);
  const [newPeer, setNewPeer] = useState({
    ip: "",
    api_port: 8000,
  });
  const [addingPeer, setAddingPeer] = useState(false);

  //Fetch P2P configuration
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

  //Fetch P2P status
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

  //Fetch sync state
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

  //Initial load
  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      await Promise.all([fetchP2PConfig(), fetchP2PStatus(), fetchSyncState()]);
      setLoading(false);
    };
    loadAll();

    //Auto refresh config, status, and sync state every 10s
    const interval = setInterval(() => {
      fetchP2PConfig(); // Auto-refresh config to detect changes from other sources
      fetchP2PStatus();
      fetchSyncState();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  //Update this central config
  const updateThisCentral = (key, value) => {
    setP2pConfig((prev) => ({
      ...prev,
      this_central: {
        ...prev.this_central,
        [key]: value,
      },
    }));
  };

  //Add peer central with bi-directional registration
  const handleAddPeer = async () => {
    if (!newPeer.ip.trim()) {
      setMessage({
        type: "error",
        text: "Vui lòng nhập IP address",
      });
      return;
    }

    try {
      setAddingPeer(true);
      setMessage({
        type: "info",
        text: "Đang kết nối và đăng ký với peer...",
      });

      const response = await fetch(`${CENTRAL_URL}/api/p2p/add-peer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ip: newPeer.ip.trim(),
          api_port: newPeer.api_port,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setMessage({
          type: "success",
          text: data.message,
        });

        // Reload config to show the new peer
        await fetchP2PConfig();
        await fetchP2PStatus();

        setNewPeer({ ip: "", api_port: 8000 });
        setShowAddPeer(false);
      } else {
        setMessage({
          type: "error",
          text: `Lỗi: ${data.error || "Không thể thêm peer"}`,
        });
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: `Không thể kết nối: ${err.message}`,
      });
    } finally {
      setAddingPeer(false);
    }
  };

  //Remove peer central with bi-directional unregistration
  const handleRemovePeer = async (peerId) => {
    if (!window.confirm(`Bạn có chắc muốn xóa peer "${peerId}"?`)) {
      return;
    }

    try {
      // Find peer info
      const peer = p2pConfig.peer_centrals.find((p) => p.id === peerId);
      if (!peer) {
        setMessage({
          type: "error",
          text: `Không tìm thấy peer "${peerId}"`,
        });
        return;
      }

      // Get this central's ID
      const thisCentralId = p2pConfig.this_central?.id;

      // Remove from local config
      const updatedConfig = {
        ...p2pConfig,
        peer_centrals: p2pConfig.peer_centrals.filter((p) => p.id !== peerId),
      };

      // Save local config
      const saveResponse = await fetch(`${CENTRAL_URL}/api/p2p/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updatedConfig),
      });

      const saveData = await saveResponse.json();
      if (!saveData.success) {
        setMessage({
          type: "error",
          text: `Lỗi khi lưu config: ${saveData.error}`,
        });
        return;
      }

      // Try to unregister from peer (bi-directional)
      try {
        const peerApiUrl = `http://${peer.ip}:${peer.api_port || 8000}`;
        const unregisterUrl = `${peerApiUrl}/api/p2p/unregister-peer?peer_id=${thisCentralId}`;

        await fetch(unregisterUrl, {
          method: "POST",
          timeout: 5000,
        });
      } catch (e) {
        console.warn(`Could not unregister from peer ${peerId}:`, e);
        // Continue even if unregistration fails
      }

      // Reload config
      await fetchP2PConfig();
      await fetchP2PStatus();

      setMessage({
        type: "success",
        text: `Đã xóa peer "${peerId}" và thông báo cho peer`,
      });
    } catch (error) {
      setMessage({
        type: "error",
        text: `Lỗi khi xóa peer: ${error.message}`,
      });
    }
  };

  //Update peer central
  const updatePeer = (peerId, key, value) => {
    setP2pConfig((prev) => ({
      ...prev,
      peer_centrals: prev.peer_centrals.map((peer) =>
        peer.id === peerId ? { ...peer, [key]: value } : peer
      ),
    }));
  };

  //Test connection to peer
  const handleTestConnection = async (peerId) => {
    try {
      setMessage({
        type: "info",
        text: `Đang kiểm tra kết nối đến "${peerId}"...`,
      });

      const response = await fetch(
        `${CENTRAL_URL}/api/p2p/test-connection?peer_id=${peerId}`,
        { method: "POST" }
      );

      const data = await response.json();
      if (data.success) {
        setMessage({
          type: "success",
          text: `Kết nối thành công đến "${peerId}"`,
        });
      } else {
        setMessage({
          type: "error",
          text: `Không thể kết nối đến "${peerId}": ${data.error}`,
        });
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: `Lỗi khi kiểm tra kết nối: ${err.message}`,
      });
    }
  };

  //Get peer connection status
  const getPeerStatus = (peerId) => {
    if (!p2pStatus || !p2pStatus.peers) return "unknown";
    const peer = p2pStatus.peers.find((p) => p.peer_id === peerId);
    return peer ? peer.status : "unknown";
  };

  //Get last sync info
  const getSyncInfo = (peerId) => {
    const sync = syncState.find((s) => s.peer_central_id === peerId);
    return sync;
  };

  //Format timestamp
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
            <div className="col-md-4">
              <label className="form-label small">API Port</label>
              <input
                type="number"
                className="form-control form-control-sm"
                value={p2pConfig.this_central?.api_port || 8000}
                onChange={(e) =>
                  updateThisCentral("api_port", parseInt(e.target.value))
                }
              />
              <small className="text-muted">
                Port cho cả HTTP API và WebSocket P2P
              </small>
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
                  Thêm Peer Central mới (chỉ cần IP)
                </h6>
                <div className="alert alert-info small mb-3">
                  <i className="bi bi-info-circle me-2"></i>
                  Chỉ cần nhập IP của peer. ID sẽ được tự động lấy từ peer, và
                  cả 2 central sẽ tự động đăng ký với nhau.
                </div>
                <div className="row g-2">
                  <div className="col-md-8">
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
                      disabled={addingPeer}
                    />
                  </div>
                  <div className="col-md-4">
                    <label className="form-label small">API Port</label>
                    <input
                      type="number"
                      className="form-control form-control-sm"
                      value={newPeer.api_port}
                      onChange={(e) =>
                        setNewPeer({
                          ...newPeer,
                          api_port: parseInt(e.target.value),
                        })
                      }
                      disabled={addingPeer}
                    />
                  </div>
                </div>
                <div className="mt-2 d-flex gap-2">
                  <button
                    className="btn btn-sm btn-success"
                    onClick={handleAddPeer}
                    disabled={addingPeer}
                  >
                    {addingPeer ? (
                      <>
                        <span className="spinner-border spinner-border-sm me-1"></span>
                        Đang thêm...
                      </>
                    ) : (
                      <>
                        <i className="bi bi-check-circle me-1"></i>
                        Thêm & Đăng ký
                      </>
                    )}
                  </button>
                  <button
                    className="btn btn-sm btn-secondary"
                    onClick={() => {
                      setShowAddPeer(false);
                      setNewPeer({ ip: "", api_port: 8000 });
                    }}
                    disabled={addingPeer}
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
                    <th style={{ width: "30%" }}>IP Address</th>
                    <th style={{ width: "15%" }}>Trạng thái</th>
                    <th style={{ width: "20%" }}>Sync lần cuối</th>
                    <th style={{ width: "15%" }} className="text-end">
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
    </div>
  );
};

export default P2PSettings;
