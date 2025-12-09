/**
 * Component hiển thị thông báo
 */
const Notification = ({ message }) => {
  const getAlertType = () => {
    if (
      message.includes("Đã lưu") ||
      message.includes("thành công")
    ) {
      return "alert-success";
    }
    if (
      message.includes("Lỗi") ||
      message.includes("Không thể")
    ) {
      return "alert-danger";
    }
    if (message.includes("Đang")) {
      return "alert-info";
    }
    return "alert-info";
  };

  const getIcon = () => {
    if (
      message.includes("Đã lưu") ||
      message.includes("thành công")
    ) {
      return "bi-check-circle-fill";
    }
    if (
      message.includes("Lỗi") ||
      message.includes("Không thể")
    ) {
      return "bi-exclamation-triangle-fill";
    }
    if (message.includes("Đang đọc")) {
      return "bi-search";
    }
    return "bi-info-circle-fill";
  };

  return (
    //Luon render mot container co chieu cao toi thieu de khong day cao/thap camera giua cac cong
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
