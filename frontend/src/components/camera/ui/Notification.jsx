/**
 * Component hiển thị thông báo
 */
const Notification = ({ message }) => {
  const getAlertType = () => {
    if (
      message.includes("✅") ||
      message.includes("thành công") ||
      message.includes("🚪 Cửa đã mở")
    ) {
      return "alert-success";
    }
    if (
      message.includes("❌") ||
      message.includes("Lỗi") ||
      message.includes("Không thể")
    ) {
      return "alert-danger";
    }
    if (message.includes("🔒") || message.includes("Đang đóng")) {
      return "alert-info";
    }
    return "alert-info";
  };

  const getIcon = () => {
    if (
      message.includes("✅") ||
      message.includes("thành công") ||
      message.includes("🚪 Cửa đã mở")
    ) {
      return "bi-check-circle-fill";
    }
    if (
      message.includes("❌") ||
      message.includes("Lỗi") ||
      message.includes("Không thể")
    ) {
      return "bi-exclamation-triangle-fill";
    }
    if (message.includes("🔒") || message.includes("Đang đóng")) {
      return "bi-lock-fill";
    }
    return "bi-info-circle-fill";
  };

  return (
    // Luôn render một container có chiều cao tối thiểu để không đẩy cao/thấp camera giữa các cổng
    <div style={{ minHeight: "40px", marginBottom: "0.5rem" }}>
      {message && (
        <div
          className={`${getAlertType()} py-2 px-3`}
          style={{ fontSize: "0.9rem" }}
        >
          <div className="d-flex align-items-center">
            <i className={`bi ${getIcon()} me-2`}></i>
            <span>{message}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default Notification;
