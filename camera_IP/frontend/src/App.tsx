import React, { useState, useEffect } from "react";
import { CameraGrid } from "./components/CameraGrid";
import { AddCameraModal } from "./components/AddCameraModal";
import { EditCameraModal } from "./components/EditCameraModal";
import { backendApi } from "./services/backendApi";
import type { Camera } from "./types/camera";

function App() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [loading, setLoading] = useState(true);

  // Load cameras from backend API (reads from go2rtc.yaml)
  useEffect(() => {
    const loadCameras = async () => {
      try {
        const cameras = await backendApi.getCameras();
        setCameras(cameras);
      } catch (error) {
        alert(
          "Failed to connect to backend API. Make sure backend is running on port 5000."
        );
      }
      setLoading(false);
    };

    loadCameras();
  }, []);

  const handleAddCamera = async (camera: Camera) => {
    try {
      // Backend will:
      // 1. Save to YAML file (persistent across restarts)
      // 2. Add to go2rtc runtime (immediate, no restart needed)
      await backendApi.addCamera(camera);

      // Update UI immediately
      setCameras((prev) => [...prev, camera]);
    } catch (error) {
      alert("Failed to add camera. Please check the backend is running.");
    }
  };

  const handleEditCamera = (camera: Camera) => {
    setEditingCamera(camera);
    setShowEditModal(true);
  };

  const handleUpdateCamera = async (updatedCamera: Camera) => {
    try {
      await backendApi.updateCamera(updatedCamera);

      setCameras((prev) =>
        prev.map((cam) => (cam.id === updatedCamera.id ? updatedCamera : cam))
      );

      setShowEditModal(false);
      setEditingCamera(null);
    } catch (error) {
      alert("Failed to update camera. Please check the backend is running.");
    }
  };

  const handleRemoveCamera = async (cameraId: string) => {
    const confirmed = window.confirm(
      "Are you sure you want to remove this camera?"
    );
    if (!confirmed) return;

    try {
      // Backend will:
      // 1. Remove from YAML file (persistent)
      // 2. Remove from go2rtc runtime (immediate)
      await backendApi.removeCamera(cameraId);

      setCameras((prev) => prev.filter((cam) => cam.id !== cameraId));
    } catch (error) {
      alert("Failed to remove camera. Please check the backend is running.");
    }
  };

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center min-vh-100">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-vh-100 bg-dark">
      {/* Header */}
      <nav className="navbar navbar-dark bg-black border-bottom border-secondary">
        <div className="container-fluid">
          <span className="navbar-brand mb-0 h1">
            <i className="bi bi-camera-video-fill me-2"></i>
            Camera Stream Monitor
          </span>
          <button
            className="btn btn-primary"
            onClick={() => setShowModal(true)}
          >
            <i className="bi bi-plus-circle me-2"></i>
            Add Camera
          </button>
        </div>
      </nav>

      {/* Main Content */}
      <div className="container-fluid py-4">
        <CameraGrid
          cameras={cameras}
          onRemoveCamera={handleRemoveCamera}
          onEditCamera={handleEditCamera}
        />
      </div>

      {/* Add Camera Modal */}
      <AddCameraModal
        show={showModal}
        onClose={() => setShowModal(false)}
        onAdd={handleAddCamera}
      />

      {/* Edit Camera Modal */}
      <EditCameraModal
        show={showEditModal}
        camera={editingCamera}
        onClose={() => {
          setShowEditModal(false);
          setEditingCamera(null);
        }}
        onUpdate={handleUpdateCamera}
      />
    </div>
  );
}

export default App;
