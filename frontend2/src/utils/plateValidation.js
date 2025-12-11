/**
 * Validate biển số Việt Nam
 * Format: 2 số + 1-2 chữ cái + 4-6 số
 * VD: 30A12345, 30AB1234, 29A123456
 */
export const validatePlateNumber = (plateText) => {
  if (!plateText || plateText.trim().length < 5) {
    return false;
  }

  const normalizedPlate = plateText
    .trim()
    .toUpperCase()
    .replace(/[-.\s]/g, "");

  const platePattern = /^[0-9]{2}[A-Z]{1,2}[0-9]{4,6}$/;

  return platePattern.test(normalizedPlate);
};

/**
 * Normalize biển số (loại bỏ khoảng trắng, dấu gạch ngang, chuyển thành chữ hoa)
 */
export const normalizePlateNumber = (plateText) => {
  if (!plateText) return "";
  return plateText.trim().toUpperCase().replace(/[-.\s]/g, "");
};

