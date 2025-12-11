/**
 * Header component cho CameraView
 * Hiển thị tên camera, loại cổng và trạng thái kết nối
 */
const CameraHeader = ({ cameraInfo, isConnected, isFullscreen }) => {
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
              cameraInfo.type === "ENTRY"
                ? "bg-success"
                : cameraInfo.type === "EXIT"
                ? "bg-danger"
                : "bg-secondary"
            }`}
          >
            {cameraInfo.type === "ENTRY"
              ? "VÀO"
              : cameraInfo.type === "EXIT"
              ? "RA"
              : "TRONG BÃI"}
          </span>
        )}

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
