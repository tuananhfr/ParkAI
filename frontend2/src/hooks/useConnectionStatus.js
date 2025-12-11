import { useState, useEffect, useCallback } from "react";
import { CENTRAL_URL } from "../config";

/**
 * Global Connection Status Manager
 *
 * Monitors backend connection status and provides:
 * - isConnected: boolean (backend online/offline)
 * - lastConnectedTime: timestamp của lần connected cuối
 * - retry mechanism: tự động retry khi backend down
 *
 * Usage:
 *   const { isConnected, checkConnection } = useConnectionStatus();
 */

//Global state de share giua tat ca components
let globalIsConnected = null;
let globalLastConnectedTime = null;
let globalLastDisconnectedTime = null;
let globalListeners = new Set();
let globalCheckTimer = null;

const notifyListeners = () => {
  globalListeners.forEach((listener) => {
    listener({
      isConnected: globalIsConnected,
      lastConnectedTime: globalLastConnectedTime,
      lastDisconnectedTime: globalLastDisconnectedTime,
    });
  });
};

const checkBackendHealth = async () => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); //5s timeout

    const response = await fetch(`${CENTRAL_URL}/api/status`, {
      method: "GET",
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      const wasDisconnected = globalIsConnected === false;
      const previousState = globalIsConnected;

      globalIsConnected = true;
      globalLastConnectedTime = Date.now();

      //CHI notify khi la reconnect thuc su (false → true), KHONG phai initial (null → true)
      if (wasDisconnected && previousState === false) {
        console.log("[Connection] Backend reconnected!");
      }

      notifyListeners();
      return true;
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (err) {
    const wasConnected = globalIsConnected === true;
    globalIsConnected = false;
    globalLastDisconnectedTime = Date.now();

    if (wasConnected) {
      console.log("[Connection] Backend disconnected:", err.message);
    }

    notifyListeners();
    return false;
  }
};

const startGlobalHealthCheck = () => {
  if (globalCheckTimer) return; //Already running

  //Check ngay lap tuc
  checkBackendHealth();

  //Sau do check moi 5 giay
  globalCheckTimer = setInterval(() => {
    checkBackendHealth();
  }, 5000);
};

const stopGlobalHealthCheck = () => {
  if (globalCheckTimer) {
    clearInterval(globalCheckTimer);
    globalCheckTimer = null;
  }
};

const useConnectionStatus = () => {
  const [state, setState] = useState({
    isConnected: globalIsConnected,
    lastConnectedTime: globalLastConnectedTime,
    lastDisconnectedTime: globalLastDisconnectedTime,
  });

  useEffect(() => {
    //Register listener
    const listener = (newState) => {
      setState(newState);
    };
    globalListeners.add(listener);

    //Start global health check neu chua chay
    startGlobalHealthCheck();

    return () => {
      //Unregister listener
      globalListeners.delete(listener);

      //Stop health check neu khong con listeners
      if (globalListeners.size === 0) {
        stopGlobalHealthCheck();
      }
    };
  }, []);

  const checkConnection = useCallback(async () => {
    return await checkBackendHealth();
  }, []);

  return {
    isConnected: state.isConnected,
    lastConnectedTime: state.lastConnectedTime,
    lastDisconnectedTime: state.lastDisconnectedTime,
    checkConnection,
  };
};

export default useConnectionStatus;
