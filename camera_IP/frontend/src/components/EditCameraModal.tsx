import { useState, useEffect } from 'react';
import type { Camera, CameraType } from '../types/camera';

interface EditCameraModalProps {
  show: boolean;
  camera: Camera | null;
  onClose: () => void;
  onUpdate: (camera: Camera) => void;
}

export const EditCameraModal = ({ show, camera, onClose, onUpdate }: EditCameraModalProps) => {
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

  // Parse RTSP URL to extract username, password, and host
  const parseRtspUrl = (rtspUrl: string) => {
    try {
      // Format: rtsp://username:password@host/path
      const match = rtspUrl.match(/^rtsp:\/\/([^:]+):([^@]+)@(.+)$/);
      if (match) {
        return {
          username: match[1],
          password: match[2],
          host: match[3],
        };
      }
    } catch (e) {
      // If parsing fails, return empty values
    }
    return { username: '', password: '', host: rtspUrl };
  };

  // Pre-fill form when camera changes
  useEffect(() => {
    if (camera) {
      setName(camera.name);
      setType(camera.type);

      if (camera.type === 'rtsp') {
        const parsed = parseRtspUrl(camera.url);
        setHost(parsed.host);
        setUsername(parsed.username);
        setPassword(parsed.password);
      } else {
        setUrl(camera.url);
      }
    }
  }, [camera]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!camera) return;

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
      finalUrl = `rtsp://${username.trim()}:${password.trim()}@${host.trim()}`;
    } else {
      finalUrl = url.trim();
    }

    // Create updated camera object
    const updatedCamera: Camera = {
      id: camera.id,
      name: name.trim(),
      type,
      url: finalUrl,
    };

    onUpdate(updatedCamera);
    onClose();
  };

  const handleClose = () => {
    setErrors({});
    onClose();
  };

  if (!show || !camera) return null;

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
                <i className="bi bi-pencil-square me-2"></i>
                Edit Camera
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
                  <label htmlFor="editCameraName" className="form-label">
                    Camera Name <span className="text-danger">*</span>
                  </label>
                  <input
                    type="text"
                    className={`form-control ${errors.name ? 'is-invalid' : ''}`}
                    id="editCameraName"
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
                      name="editCameraType"
                      id="editTypeRtsp"
                      checked={type === 'rtsp'}
                      onChange={() => setType('rtsp')}
                    />
                    <label className="btn btn-outline-primary" htmlFor="editTypeRtsp">
                      <i className="bi bi-hdd-network me-2"></i>
                      RTSP Camera
                    </label>

                    <input
                      type="radio"
                      className="btn-check"
                      name="editCameraType"
                      id="editTypePublic"
                      checked={type === 'public'}
                      onChange={() => setType('public')}
                    />
                    <label className="btn btn-outline-primary" htmlFor="editTypePublic">
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
                      <label htmlFor="editCameraHost" className="form-label">
                        Host/IP Address <span className="text-danger">*</span>
                      </label>
                      <input
                        type="text"
                        className={`form-control ${errors.host ? 'is-invalid' : ''}`}
                        id="editCameraHost"
                        placeholder="192.168.0.156/1/stream1"
                        value={host}
                        onChange={(e) => {
                          setHost(e.target.value);
                          setErrors({ ...errors, host: undefined });
                        }}
                      />
                      {errors.host && (
                        <div className="invalid-feedback">{errors.host}</div>
                      )}
                    </div>

                    {/* Username */}
                    <div className="mb-3">
                      <label htmlFor="editCameraUsername" className="form-label">
                        Username <span className="text-danger">*</span>
                      </label>
                      <input
                        type="text"
                        className={`form-control ${errors.username ? 'is-invalid' : ''}`}
                        id="editCameraUsername"
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
                      <label htmlFor="editCameraPassword" className="form-label">
                        Password <span className="text-danger">*</span>
                      </label>
                      <input
                        type="password"
                        className={`form-control ${errors.password ? 'is-invalid' : ''}`}
                        id="editCameraPassword"
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
                      <label htmlFor="editCameraUrl" className="form-label">
                        Stream URL <span className="text-danger">*</span>
                      </label>
                      <input
                        type="text"
                        className={`form-control ${errors.url ? 'is-invalid' : ''}`}
                        id="editCameraUrl"
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
                  <i className="bi bi-check-circle me-2"></i>
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  );
};
