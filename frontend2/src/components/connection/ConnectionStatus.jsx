import { useState, useEffect } from "react";
import useConnectionStatus from "../../hooks/useConnectionStatus";

/**
 * ConnectionStatus - Hiển thị trạng thái kết nối backend
 *
 * - Hiển thị banner khi mất kết nối
 * - Tự động ẩn khi reconnect thành công
 * - Hiển thị thời gian mất kết nối
 */
const ConnectionStatus = () => {
  const { isConnected, lastDisconnectedTime } = useConnectionStatus();
  const [disconnectedDuration, setDisconnectedDuration] = useState(0);
  const [showReconnected, setShowReconnected] = useState(false);
  const [previousConnection, setPreviousConnection] = useState(null);

  //Track connection state changes de detect reconnect
  useEffect(() => {
    if (isConnected !== null && isConnected !== previousConnection) {
      //State changed
      if (isConnected === true && previousConnection === false) {
        //Reconnected! (false → true)
        setShowReconnected(true);
        const timer = setTimeout(() => {
          setShowReconnected(false);
        }, 3000); //Hide after 3s

        return () => clearTimeout(timer);
      }
      setPreviousConnection(isConnected);
    }
  }, [isConnected, previousConnection]);

  //Update disconnected duration moi giay
  useEffect(() => {
    if (isConnected === false && lastDisconnectedTime) {
      const interval = setInterval(() => {
        const duration = Math.floor(
          (Date.now() - lastDisconnectedTime) / 1000
        );
        setDisconnectedDuration(duration);
      }, 1000);

      return () => clearInterval(interval);
    }
  }, [isConnected, lastDisconnectedTime]);

  //Khong hien thi gi neu chua biet trang thai (initial load)
  if (isConnected === null) {
    return null;
  }

  //Hien thi banner "reconnected" (success)
  if (showReconnected && isConnected) {
    return (
      <div
        className="alert alert-success mb-0 py-2 px-3 d-flex align-items-center justify-content-between"
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 9999,
          borderRadius: 0,
          animation: "slideDown 0.3s ease-out",
        }}
      >
        <div className="d-flex align-items-center">
          <i className="bi bi-check-circle-fill me-2"></i>
          <strong>Đã kết nối lại với backend</strong>
        </div>
      </div>
    );
  }

  //Hien thi banner "disconnected" (danger)
  if (!isConnected) {
    return (
      <div
        className="alert alert-danger mb-0 py-2 px-3 d-flex align-items-center justify-content-between"
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 9999,
          borderRadius: 0,
          animation: "slideDown 0.3s ease-out",
        }}
      >
        <div className="d-flex align-items-center">
          <div className="spinner-border spinner-border-sm me-2" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <strong>Mất kết nối với backend</strong>
          {disconnectedDuration > 0 && (
            <span className="ms-2 badge bg-dark">
              {disconnectedDuration}s
            </span>
          )}
        </div>
        <small className="text-muted">Đang thử kết nối lại...</small>
      </div>
    );
  }

  //Connected va khong can hien thi gi
  return null;
};

export default ConnectionStatus;
