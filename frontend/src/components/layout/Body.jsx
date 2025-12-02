import CameraView from "../camera/CameraView";

/**
 * AppBody - Component body hiển thị cameras grid
 */
const Body = ({ cameras, onHistoryUpdate }) => {
  return (
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
              <CameraView camera={camera} onHistoryUpdate={onHistoryUpdate} />
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default Body;
