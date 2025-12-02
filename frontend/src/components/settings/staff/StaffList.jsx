import { useState, useEffect } from "react";
import { CENTRAL_URL } from "@/config";

/**
 * StaffList - Component hiển thị danh sách người trực
 */
const StaffList = ({ apiUrl }) => {
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStaff();
  }, [apiUrl]);

  const fetchStaff = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${CENTRAL_URL}/api/staff`);
      const data = await response.json();
      if (data.success) {
        setStaff(data.staff || []);
      } else {
        setError(data.error || "Không thể tải danh sách người trực");
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

  if (!staff || staff.length === 0) {
    return (
      <div className="alert alert-info">
        <i className="bi bi-info-circle me-2"></i>
        Chưa có dữ liệu người trực
      </div>
    );
  }

  return (
    <div>
      <div className="mb-2">
        <small className="text-muted">
          <i className="bi bi-info-circle me-1"></i>
          Tổng số: {staff.length} người trực
        </small>
      </div>
      <div className="table-responsive">
        <table className="table table-sm table-striped table-hover">
          <thead>
            <tr>
              <th>ID</th>
              <th>Tên</th>
              <th>Chức vụ</th>
              <th>Số điện thoại</th>
              <th>Ca trực</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {staff.map((person) => (
              <tr key={person.id}>
                <td>{person.id}</td>
                <td>{person.name}</td>
                <td>{person.position || "-"}</td>
                <td>{person.phone || "-"}</td>
                <td>
                  <span
                    className={`badge ${
                      person.shift === "Ca ngày"
                        ? "bg-info"
                        : person.shift === "Ca đêm"
                        ? "bg-dark"
                        : "bg-secondary"
                    }`}
                  >
                    {person.shift || "-"}
                  </span>
                </td>
                <td>
                  <span
                    className={`badge ${
                      person.status === "active" ? "bg-success" : "bg-secondary"
                    }`}
                  >
                    {person.status === "active" ? "Hoạt động" : "Nghỉ"}
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

export default StaffList;
