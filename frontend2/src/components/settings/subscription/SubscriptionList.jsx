import { useState, useEffect } from "react";
import { CENTRAL_URL } from "@/config";

/**
 * SubscriptionList - Component hiển thị danh sách thuê bao (read-only)
 */
const SubscriptionList = ({ apiUrl }) => {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchSubscriptions();
  }, [apiUrl]);

  const fetchSubscriptions = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${CENTRAL_URL}/api/subscriptions`);
      const data = await response.json();
      if (data.success) {
        setSubscriptions(data.subscriptions || []);
      } else {
        setError(data.error || "Không thể tải danh sách thuê bao");
      }
    } catch (err) {
      setError("Không thể kết nối đến server");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-3">
        <div className="spinner-border spinner-border-sm text-primary"></div>
        <small className="d-block mt-2 text-muted">Đang tải...</small>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-warning">
        <i className="bi bi-exclamation-triangle me-2"></i>
        {error}
      </div>
    );
  }

  if (!subscriptions || subscriptions.length === 0) {
    return (
      <div className="alert alert-info">
        <i className="bi bi-info-circle me-2"></i>
        Chưa có dữ liệu thuê bao
      </div>
    );
  }

  const getTypeLabel = (type) => {
    switch (type) {
      case "company":
        return "Thẻ công ty";
      case "monthly":
        return "Thẻ tháng";
      case "regular":
        return "Khách lẻ";
      default:
        return type;
    }
  };

  const getTypeBadge = (type) => {
    switch (type) {
      case "company":
        return "bg-primary";
      case "monthly":
        return "bg-info";
      case "regular":
        return "bg-warning";
      default:
        return "bg-secondary";
    }
  };

  return (
    <div>
      <div className="mb-2">
        <small className="text-muted">
          <i className="bi bi-info-circle me-1"></i>
          Tổng số: {subscriptions.length} thuê bao
        </small>
      </div>
      <div className="table-responsive">
        <table className="table table-sm table-striped table-hover">
          <thead>
            <tr>
              <th>Biển số</th>
              <th>Chủ xe</th>
              <th>Loại</th>
              <th>SĐT</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) => (
              <tr key={sub.id}>
                <td>
                  <strong>{sub.plate_number}</strong>
                </td>
                <td>{sub.owner_name || "-"}</td>
                <td>
                  <span className={`badge ${getTypeBadge(sub.type)}`}>
                    {getTypeLabel(sub.type)}
                  </span>
                </td>
                <td>{sub.phone || "-"}</td>
                <td>
                  <span
                    className={`badge ${
                      sub.status === "active" ? "bg-success" : "bg-secondary"
                    }`}
                  >
                    {sub.status === "active" ? "Hoạt động" : "Nghỉ"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SubscriptionList;
