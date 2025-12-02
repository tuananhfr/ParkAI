import { useState, useEffect } from "react";
import { CENTRAL_URL } from "../config";

/**
 * Custom hook để quản lý stats (header info)
 * - Fetch lần đầu + interval fallback
 * - Lắng nghe WebSocket /ws/history để cập nhật realtime khi có thay đổi history
 */
const useStats = () => {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    // Fetch stats NGAY để có UI nhanh
    fetchStats();

    // WebSocket lắng nghe history_update → cập nhật stats realtime
    const wsUrl = CENTRAL_URL.replace("http", "ws") + "/ws/history";
    let ws = null;
    let reconnectTimer = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          // console.log("[Stats] WebSocket connected");
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            if (message.type === "history_update") {
              // Khi có thay đổi history (vào/ra/sửa/xóa) → refetch stats
              fetchStats();
            }
          } catch (err) {
            console.error("[Stats] WebSocket message error:", err);
          }
        };

        ws.onclose = () => {
          // console.log("[Stats] WebSocket disconnected, reconnecting...");
          reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = (err) => {
          console.error("[Stats] WebSocket error:", err);
        };
      } catch (err) {
        console.error("[Stats] WebSocket connection error:", err);
      }
    };

    connect();

    return () => {
      if (ws) {
        ws.close();
      }
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
    };
  }, []);

  const fetchStats = async () => {
    try {
      // Gọi API stats chuyên biệt
      const response = await fetch(`${CENTRAL_URL}/api/stats`);
      const data = await response.json();
      if (data.success) {
        // /api/stats trả trực tiếp fields stats
        setStats({
          entries_today: data.entries_today,
          exits_today: data.exits_today,
          vehicles_in_parking: data.vehicles_in_parking,
          revenue_today: data.revenue_today,
        });
      }
    } catch (err) {
      // Silent fail
    }
  };

  return { stats };
};

export default useStats;

