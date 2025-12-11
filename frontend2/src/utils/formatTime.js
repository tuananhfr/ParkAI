/**
 * Format thời gian theo định dạng: h:m:s d/m/y
 */
export const formatTime = (date) => {
  if (!date) return "";

  const d = date instanceof Date ? date : new Date(date);

  const pad = (n) => n.toString().padStart(2, "0");

  const hours = pad(d.getHours());
  const minutes = pad(d.getMinutes());
  const seconds = pad(d.getSeconds());

  const day = pad(d.getDate());
  const month = pad(d.getMonth() + 1);
  const year = d.getFullYear();

  return `${hours}:${minutes}:${seconds} ${day}/${month}/${year}`;
};
