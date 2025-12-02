/**
 * Format thời gian theo định dạng Việt Nam
 */
export const formatTime = (date) =>
  date.toLocaleString("vi-VN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

