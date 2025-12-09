import { useState, useEffect } from "react";

/**
 * CentralSyncServersList - Component quản lý danh sách máy chủ central để đồng bộ
 */
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

export default CentralSyncServersList;
