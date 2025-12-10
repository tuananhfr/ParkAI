import { useState, useEffect } from "react";
import { validatePlateNumber } from "@/utils/plateValidation";

/**
 * Input biển số xe - có thể nhập trực tiếp và nhấn Enter để validate
 */
const PlateInput = ({
  plateText,
  plateSource,
  onPlateConfirm,
  onPlateChange,
}) => {
  const [inputValue, setInputValue] = useState(plateText || "");
  const [isEditing, setIsEditing] = useState(false);

  //Sync voi plateText tu props (khi co detection tu camera)
  useEffect(() => {
    if (!isEditing && plateText !== inputValue) {
      setInputValue(plateText || "");
    }
  }, [plateText, isEditing]);

  const handleInputChange = (e) => {
    const value = e.target.value.toUpperCase();
    setInputValue(value);
    setIsEditing(true);
    if (onPlateChange) {
      onPlateChange(value);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      handleConfirm();
    }
  };

  const handleConfirm = () => {
    const normalizedPlate = inputValue.trim().toUpperCase();

    if (!normalizedPlate || normalizedPlate.length < 5) {
      if (onPlateConfirm) {
        onPlateConfirm(null, "Biển số phải có ít nhất 5 ký tự!");
      }
      return;
    }

    if (!validatePlateNumber(normalizedPlate)) {
      if (onPlateConfirm) {
        onPlateConfirm(
          null,
          "Biển số không hợp lệ! Vui lòng nhập đúng định dạng (VD: 30A12345)"
        );
      }
      return;
    }

    setInputValue(normalizedPlate);
    setIsEditing(false);
    if (onPlateConfirm) {
      onPlateConfirm(normalizedPlate, "Đã cập nhật biển số!");
    }
  };

  const handleBlur = () => {
    //Khi blur, neu dang edit thi confirm
    if (isEditing && inputValue.trim()) {
      handleConfirm();
    } else {
      setIsEditing(false);
    }
  };

  return (
    <div className="mb-2">
      <label className="form-label small mb-1 text-secondary">Biển số xe</label>
      <input
        type="text"
        value={inputValue}
        onChange={handleInputChange}
        onKeyPress={handleKeyPress}
        onBlur={handleBlur}
        className="form-control form-control-sm text-center fw-bold text-uppercase"
        placeholder="Chờ quét hoặc nhập tay và nhấn Enter..."
        style={{
          letterSpacing: "1px",
        }}
      />
    </div>
  );
};

export default PlateInput;
