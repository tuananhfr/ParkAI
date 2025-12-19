import { VideoPlayerWithDetection } from './VideoPlayerWithDetection';
import type { Camera } from '../types/camera';

interface CameraGridProps {
  cameras: Camera[];
  onRemoveCamera: (cameraId: string) => void;
  onEditCamera: (camera: Camera) => void;
}

export const CameraGrid = ({ cameras, onRemoveCamera, onEditCamera }: CameraGridProps) => {
  if (cameras.length === 0) {
    return (
      <div className="alert alert-info text-center" role="alert">
        <i className="bi bi-camera-video-off fs-1 d-block mb-3"></i>
        <h4>No cameras added yet</h4>
        <p className="mb-0">Click the "Add Camera" button to start streaming</p>
      </div>
    );
  }

  return (
    <div className="row g-3">
      {cameras.map((camera) => (
        <div key={camera.id} className="col-12 col-md-6 col-xl-4">
          <VideoPlayerWithDetection
            camera={camera}
            onRemove={onRemoveCamera}
            onEdit={onEditCamera}
            enableDetection={true}
          />
        </div>
      ))}
    </div>
  );
};
