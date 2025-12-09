import { useState } from "react";
import { CENTRAL_URL } from "../config";

/**
 * Custom hook để quản lý staff
 */
const useStaff = () => {
  const [staff, setStaff] = useState([]);

  const fetchStaff = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/staff`);
      const data = await response.json();
      if (data.success) {
        setStaff(data.staff || []);
      }
    } catch (err) {
      console.error("[Staff] Fetch error:", err);
    }
  };

  const toggleStaffStatus = (staffId) => {
    setStaff((prev) =>
      prev.map((person) =>
        person.id === staffId
          ? {
              ...person,
              status: person.status === "active" ? "inactive" : "active",
            }
          : person
      )
    );
  };

  const saveStaffChanges = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/staff`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ staff }),
      });
      const data = await response.json();
      if (data.success) {
        //Refresh staff list
        await fetchStaff();
        return true;
      } else {
        alert(`Lỗi: ${data.error || "Không thể lưu thay đổi"}`);
        return false;
      }
    } catch (err) {
      alert("Không thể kết nối đến server");
      return false;
    }
  };

  return {
    staff,
    fetchStaff,
    toggleStaffStatus,
    saveStaffChanges,
  };
};

export default useStaff;

