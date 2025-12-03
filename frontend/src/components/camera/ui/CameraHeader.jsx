/**
 * Header component cho CameraView
 * Hiển thị tên camera, loại cổng, trạng thái barrier và kết nối
 */
const CameraHeader = ({
  cameraInfo,
  barrierStatus,
  isConnected,
  isFullscreen,
}) => {
  return (
    <div
      className={`card-header bg-primary text-white d-flex justify-content-between align-items-center py-2 px-3 ${
        isFullscreen ? "d-none" : ""
      }`}
    >
      <div className="d-flex flex-column">
        {cameraInfo?.ip && (
          <small className="text-white-50" style={{ fontSize: "0.8rem" }}>
            {cameraInfo.ip}
          </small>
        )}
        <h6 className="mb-0 small">
          <i className="bi bi-camera-video-fill me-1"></i>
          {cameraInfo?.name || `Camera #${cameraInfo?.id}`}
        </h6>
      </div>
      <div className="d-flex align-items-center gap-2">
        {cameraInfo && (
          <span
            className={`badge ${
              cameraInfo.type === "ENTRY" ? "bg-success" : "bg-danger"
            }`}
          >
            {cameraInfo.type === "ENTRY" ? "VÀO" : "RA"}
          </span>
        )}

        <span
          className={`badge ${
            barrierStatus.is_open ? "bg-warning" : "bg-secondary"
          }`}
          title={
            barrierStatus.is_open ? "Barrier đang mở" : "Barrier đang đóng"
          }
        >
          <i
            className={`bi ${
              barrierStatus.is_open
                ? "bi-door-open-fill"
                : "bi-door-closed-fill"
            } me-1`}
          ></i>
          {barrierStatus.is_open ? "MỞ" : "ĐÓNG"}
        </span>

        <i
          className={`bi bi-circle-fill fs-6 ${
            isConnected ? "text-success" : "text-secondary"
          }`}
        ></i>
      </div>
    </div>
  );
};

export default CameraHeader;
