import { useState, useEffect } from "react";
import { CENTRAL_URL } from "../config";

/**
 * Custom hook để detect backend type (edge vs central)
 * - Edge: có đúng 1 camera trong edge_cameras
 * - Central: có nhiều camera hoặc có p2p_config
 */
const useBackendType = () => {
  const [backendType, setBackendType] = useState(null); // "edge" | "central" | null
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const detectBackendType = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${CENTRAL_URL}/api/config`);
        const data = await response.json();

        if (data.success && data.config) {
          // Ưu tiên backend_type trả về từ backend (central/edge)
          if (data.config.backend_type === "edge") {
            setBackendType("edge");
          } else if (data.config.backend_type === "central") {
            setBackendType("central");
          } else {
            // Fallback heuristic nếu backend cũ không trả backend_type
            const cameras = data.config?.edge_cameras || {};
            const cameraList = Object.values(cameras);

            // Edge: có đúng 1 camera
            // Central: có nhiều camera
            if (cameraList.length === 1) {
              setBackendType("edge");
            } else {
              setBackendType("central");
            }
          }
        } else {
          // Default to central nếu không detect được
          setBackendType("central");
        }
      } catch (err) {
        console.error("[useBackendType] Failed to detect backend type:", err);
        // Default to central nếu có lỗi
        setBackendType("central");
      } finally {
        setLoading(false);
      }
    };

    detectBackendType();
  }, []);

  return {
    backendType,
    loading,
    isEdge: backendType === "edge",
    isCentral: backendType === "central",
  };
};

export default useBackendType;
