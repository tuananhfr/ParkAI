import CameraView from "@/components/camera/CameraView";
import useBackendType from "@/hooks/useBackendType";

/**
 * Body - Component body hiển thị cameras grid
 */
const Body = ({ cameras, onHistoryUpdate }) => {
  const { isEdge } = useBackendType();

  // Nếu là edge và chỉ có 1 camera, hiển thị full màn hình
  const isSingleCameraEdge = isEdge && cameras.length === 1;

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
            <div
              key={camera.id}
              className={
                isSingleCameraEdge
                  ? "col-12 h-100"
                  : "col-12 col-md-6 col-lg-3 h-100"
              }
            >
              <CameraView camera={camera} onHistoryUpdate={onHistoryUpdate} />
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default Body;
