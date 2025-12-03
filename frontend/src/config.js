let centralUrl =
  import.meta.env.VITE_CENTRAL_URL || "http://192.168.0.144:8000";

// Cho phép override qua localStorage (được set từ Settings → Kết nối Frontend → Backend)
if (typeof window !== "undefined") {
  const override = window.localStorage.getItem("central_url_override");
  if (override && typeof override === "string") {
    centralUrl = override;
  }
}

export const CENTRAL_URL = centralUrl;
