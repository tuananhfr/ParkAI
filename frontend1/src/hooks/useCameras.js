import { useState, useEffect } from "react";
import { CENTRAL_URL } from "../config";
import useConnectionStatus from "./useConnectionStatus";

/**
 * Custom hook để quản lý cameras (progressive loading + WebSocket)
 * - Auto-reconnect khi backend down → up
 */
const useCameras = () => {
  const [cameras, setCameras] = useState([]);
  const { isConnected } = useConnectionStatus();
  const [previousConnection, setPreviousConnection] = useState(null);

  //Auto-refetch cameras khi backend reconnect (CHI khi false → true, KHONG phai null → true)
  useEffect(() => {
    if (
      isConnected === true &&
      previousConnection === false &&
      previousConnection !== null
    ) {
      console.log("[Cameras] Backend reconnected, reloading cameras...");
      loadCamerasProgressively();
    }
    if (isConnected !== null) {
      setPreviousConnection(isConnected);
    }
  }, [isConnected, previousConnection]);

  const loadCamerasProgressively = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/cameras`);
      const data = await response.json();

      if (data.success && data.cameras) {
        //Sort cameras by ID de load theo thu tu
        const sortedCameras = data.cameras.sort((a, b) => a.id - b.id);

        //Load tung camera voi delay 300ms de tranh overload
        for (let i = 0; i < sortedCameras.length; i++) {
          //Delay 300ms giua moi camera (ngoai tru camera dau tien)
          if (i > 0) {
            await new Promise((resolve) => setTimeout(resolve, 300));
          }

          //Add camera vao state
          setCameras((prev) => {
            const exists = prev.find((c) => c.id === sortedCameras[i].id);
            if (exists) {
              //Update existing camera
              return prev.map((c) =>
                c.id === sortedCameras[i].id ? sortedCameras[i] : c
              );
            } else {
              //Add new camera
              return [...prev, sortedCameras[i]];
            }
          });
        }

        console.log(
          `[Cameras] Loaded ${sortedCameras.length} cameras progressively`
        );
      }
    } catch (err) {
      console.error("[Cameras] Failed to load cameras:", err);
    }
  };

  useEffect(() => {
    //===== PROGRESSIVE CAMERA LOADING =====
    //Load cameras tuan tu voi delay 300ms/camera de tranh qua tai WebRTC

    //Start progressive loading NGAY
    loadCamerasProgressively();

    //WebSocket cho camera updates (CHAY SONG SONG - real-time updates)
    //Su dung CENTRAL_URL de tao WebSocket URL (ca central va edge deu co /ws/cameras)
    const wsUrl = CENTRAL_URL.replace(/^http/, "ws") + "/ws/cameras";
    let ws = null;
    let reconnectTimer = null;
    let pingInterval = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("[Cameras] WebSocket connected");

          //Start ping interval khi connection mo
          pingInterval = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              try {
                ws.send("ping");
              } catch (err) {
                console.error("[Cameras] Ping error:", err);
                if (pingInterval) clearInterval(pingInterval);
              }
            } else {
              if (pingInterval) clearInterval(pingInterval);
            }
          }, 10000); //Ping moi 10 giay
        };

        ws.onmessage = (event) => {
          try {
            const data = event.data;
            //Handle ping/pong
            if (data === "ping") {
              ws.send("pong");
              return;
            }
            if (data === "pong") {
              return;
            }

            const message = JSON.parse(data);
            if (message.type === "cameras_update" && message.data) {
              //UPDATE cameras qua WebSocket (realtime)
              setCameras(message.data.cameras || []);
            }
          } catch (err) {
            console.error("[Cameras] WebSocket message error:", err);
          }
        };

        ws.onerror = (error) => {
          console.error("[Cameras] WebSocket error:", error);
        };

        ws.onclose = () => {
          console.log("[Cameras] WebSocket disconnected, reconnecting...");
          //Cleanup ping interval
          if (pingInterval) {
            clearInterval(pingInterval);
            pingInterval = null;
          }
          //Reconnect sau 1 giay (giam tu 3s)
          reconnectTimer = setTimeout(connect, 1000);
        };
      } catch (err) {
        console.error("[Cameras] WebSocket connection error:", err);
        reconnectTimer = setTimeout(connect, 1000);
      }
    };

    connect();

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingInterval) clearInterval(pingInterval);
      if (ws) {
        ws.onclose = null; //Prevent reconnection
        ws.close();
      }
    };
  }, []);

  const fetchCameras = async () => {
    //Fallback: Fetch cameras neu WebSocket khong ket noi duoc
    try {
      const response = await fetch(`${CENTRAL_URL}/api/cameras`);
      const data = await response.json();
      if (data.success) {
        setCameras(data.cameras);
      }
    } catch (err) {
      console.error("[Cameras] Fetch error:", err);
    }
  };

  return { cameras, fetchCameras };
};

export default useCameras;

