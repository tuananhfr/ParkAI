let centralUrl =
  import.meta.env.VITE_CENTRAL_URL || "http://192.168.0.144:8000";

//Cho phep override qua localStorage (duoc set tu Settings → Ket noi Frontend → Backend)
if (typeof window !== "undefined") {
  const override = window.localStorage.getItem("central_url_override");
  if (override && typeof override === "string") {
    centralUrl = override;
  }
}

export const CENTRAL_URL = centralUrl;
