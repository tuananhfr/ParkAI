import { useState } from 'react';
import type { Camera, CameraType } from '../types/camera';

interface AddCameraModalProps {
  show: boolean;
  onClose: () => void;
  onAdd: (camera: Camera) => void;
}

export const AddCameraModal = ({ show, onClose, onAdd }: AddCameraModalProps) => {
  const [name, setName] = useState('');
  const [type, setType] = useState<CameraType>('rtsp');
  const [url, setUrl] = useState('');

  // RTSP specific fields
  const [host, setHost] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const [errors, setErrors] = useState<{
    name?: string;
    url?: string;
    host?: string;
    username?: string;
    password?: string;
  }>({});

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    const newErrors: {
      name?: string;
      url?: string;
      host?: string;
      username?: string;
      password?: string;
    } = {};

    if (!name.trim()) {
      newErrors.name = 'Camera name is required';
    }

    if (type === 'rtsp') {
      // Validate RTSP fields
      if (!host.trim()) {
        newErrors.host = 'Host/IP address is required';
      }
      if (!username.trim()) {
        newErrors.username = 'Username is required';
      }
      if (!password.trim()) {
        newErrors.password = 'Password is required';
      }
    } else {
      // Validate public stream URL
      if (!url.trim()) {
        newErrors.url = 'Stream URL is required';
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // Construct final URL
    let finalUrl = '';
    if (type === 'rtsp') {
      // Build RTSP URL: rtsp://username:password@host
      finalUrl = `rtsp://${username.trim()}:${password.trim()}@${host.trim()}`;
    } else {
      finalUrl = url.trim();
    }

    // Create camera object
    const camera: Camera = {
      id: `camera_${Date.now()}`,
      name: name.trim(),
      type,
      url: finalUrl,
    };

    onAdd(camera);

    // Reset form
    setName('');
    setUrl('');
    setHost('');
    setUsername('');
    setPassword('');
    setType('rtsp');
    setErrors({});
    onClose();
  };

  const handleClose = () => {
    setName('');
    setUrl('');
    setHost('');
    setUsername('');
    setPassword('');
    setType('rtsp');
    setErrors({});
    onClose();
  };

  if (!show) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="modal-backdrop fade show"
        onClick={handleClose}
      ></div>

      {/* Modal */}
      <div
        className="modal fade show d-block"
        tabIndex={-1}
        role="dialog"
      >
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">
                <i className="bi bi-camera-video me-2"></i>
                Add New Camera
              </h5>
              <button
                type="button"
                className="btn-close"
                onClick={handleClose}
                aria-label="Close"
              ></button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {/* Camera Name */}
                <div className="mb-3">
                  <label htmlFor="cameraName" className="form-label">
                    Camera Name <span className="text-danger">*</span>
                  </label>
                  <input
                    type="text"
                    className={`form-control ${errors.name ? 'is-invalid' : ''}`}
                    id="cameraName"
                    placeholder="e.g., Front Door, Living Room"
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value);
                      setErrors({ ...errors, name: undefined });
                    }}
                  />
                  {errors.name && (
                    <div className="invalid-feedback">{errors.name}</div>
                  )}
                </div>

                {/* Camera Type */}
                <div className="mb-3">
                  <label className="form-label">
                    Camera Type <span className="text-danger">*</span>
                  </label>
                  <div className="btn-group w-100" role="group">
                    <input
                      type="radio"
                      className="btn-check"
                      name="cameraType"
                      id="typeRtsp"
                      checked={type === 'rtsp'}
                      onChange={() => setType('rtsp')}
                    />
                    <label className="btn btn-outline-primary" htmlFor="typeRtsp">
                      <i className="bi bi-hdd-network me-2"></i>
                      RTSP Camera
                    </label>

                    <input
                      type="radio"
                      className="btn-check"
                      name="cameraType"
                      id="typePublic"
                      checked={type === 'public'}
                      onChange={() => setType('public')}
                    />
                    <label className="btn btn-outline-primary" htmlFor="typePublic">
                      <i className="bi bi-globe me-2"></i>
                      Public Stream
                    </label>
                  </div>
                </div>

                {/* RTSP Camera Fields */}
                {type === 'rtsp' ? (
                  <>
                    {/* Host/IP Address */}
                    <div className="mb-3">
                      <label htmlFor="cameraHost" className="form-label">
                        Host/IP Address <span className="text-danger">*</span>
                      </label>
                      <input
                        type="text"
                        className={`form-control ${errors.host ? 'is-invalid' : ''}`}
                        id="cameraHost"
                        placeholder="192.168.0.156/1/stream1 or 192.168.0.156:554/stream"
                        value={host}
                        onChange={(e) => {
                          setHost(e.target.value);
                          setErrors({ ...errors, host: undefined });
                        }}
                      />
                      {errors.host && (
                        <div className="invalid-feedback">{errors.host}</div>
                      )}
                      <div className="form-text">
                        Enter IP address and path (e.g., 192.168.0.156/1/stream1)
                      </div>
                    </div>

                    {/* Username */}
                    <div className="mb-3">
                      <label htmlFor="cameraUsername" className="form-label">
                        Username <span className="text-danger">*</span>
                      </label>
                      <input
                        type="text"
                        className={`form-control ${errors.username ? 'is-invalid' : ''}`}
                        id="cameraUsername"
                        placeholder="admin"
                        value={username}
                        onChange={(e) => {
                          setUsername(e.target.value);
                          setErrors({ ...errors, username: undefined });
                        }}
                      />
                      {errors.username && (
                        <div className="invalid-feedback">{errors.username}</div>
                      )}
                    </div>

                    {/* Password */}
                    <div className="mb-3">
                      <label htmlFor="cameraPassword" className="form-label">
                        Password <span className="text-danger">*</span>
                      </label>
                      <input
                        type="password"
                        className={`form-control ${errors.password ? 'is-invalid' : ''}`}
                        id="cameraPassword"
                        placeholder="Enter password"
                        value={password}
                        onChange={(e) => {
                          setPassword(e.target.value);
                          setErrors({ ...errors, password: undefined });
                        }}
                      />
                      {errors.password && (
                        <div className="invalid-feedback">{errors.password}</div>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    {/* Public Stream URL */}
                    <div className="mb-3">
                      <label htmlFor="cameraUrl" className="form-label">
                        Stream URL <span className="text-danger">*</span>
                      </label>
                      <input
                        type="text"
                        className={`form-control ${errors.url ? 'is-invalid' : ''}`}
                        id="cameraUrl"
                        placeholder="https://example.com/stream.m3u8"
                        value={url}
                        onChange={(e) => {
                          setUrl(e.target.value);
                          setErrors({ ...errors, url: undefined });
                        }}
                      />
                      {errors.url && (
                        <div className="invalid-feedback">{errors.url}</div>
                      )}
                      <div className="form-text">
                        Enter a public stream URL (HLS, RTSP, etc.)
                      </div>
                    </div>
                  </>
                )}
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleClose}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  <i className="bi bi-plus-circle me-2"></i>
                  Add Camera
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  );
};
