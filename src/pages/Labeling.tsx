import { useState } from 'react';

interface LabelData {
  licensePlate: string;
  vehicleType: string;
  color: string;
}

const Labeling = () => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [labelData, setLabelData] = useState<LabelData>({
    licensePlate: '',
    vehicleType: '',
    color: '',
  });

  // Mock data for demonstration
  const mockImages = [
    'https://via.placeholder.com/800x600/3498db/ffffff?text=Image+1',
    'https://via.placeholder.com/800x600/e74c3c/ffffff?text=Image+2',
    'https://via.placeholder.com/800x600/2ecc71/ffffff?text=Image+3',
  ];

  const vehicleTypes = ['Sedan', 'SUV', 'Truck', 'Motorcycle', 'Van', 'Other'];
  const colors = ['White', 'Black', 'Silver', 'Red', 'Blue', 'Gray', 'Green', 'Yellow', 'Other'];

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setLabelData({
      ...labelData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSave = () => {
    alert(`Saving label data: ${JSON.stringify(labelData)} (Placeholder)`);
    // TODO: Implement save logic
  };

  const handleNext = () => {
    if (currentIndex < mockImages.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setLabelData({ licensePlate: '', vehicleType: '', color: '' });
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      setLabelData({ licensePlate: '', vehicleType: '', color: '' });
    }
  };

  return (
    <div>
      <h2 className="mb-4">Labeling</h2>

      <div className="row">
        <div className="col-lg-8">
          <div className="card">
            <div className="card-header d-flex justify-content-between align-items-center">
              <h5 className="mb-0">Image Preview</h5>
              <span className="badge bg-primary">
                {currentIndex + 1} / {mockImages.length}
              </span>
            </div>
            <div className="card-body">
              <div className="position-relative" style={{ minHeight: '400px' }}>
                <img
                  src={mockImages[currentIndex]}
                  alt={`Frame ${currentIndex + 1}`}
                  className="img-fluid w-100 rounded"
                />

                {/* Bounding Box Placeholder */}
                <div
                  className="position-absolute border border-danger border-3"
                  style={{
                    top: '30%',
                    left: '35%',
                    width: '30%',
                    height: '15%',
                    pointerEvents: 'none',
                  }}
                >
                  <div className="bg-danger text-white px-2 py-1 small position-absolute" style={{ top: '-30px' }}>
                    License Plate Area
                  </div>
                </div>
              </div>

              <div className="d-flex justify-content-between mt-3">
                <button
                  className="btn btn-outline-secondary"
                  onClick={handlePrevious}
                  disabled={currentIndex === 0}
                >
                  <i className="bi bi-chevron-left me-2"></i>
                  Previous
                </button>
                <button
                  className="btn btn-outline-secondary"
                  onClick={handleNext}
                  disabled={currentIndex === mockImages.length - 1}
                >
                  Next
                  <i className="bi bi-chevron-right ms-2"></i>
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="col-lg-4">
          <div className="card">
            <div className="card-header">
              <h5 className="mb-0">Label Information</h5>
            </div>
            <div className="card-body">
              <form>
                <div className="mb-3">
                  <label htmlFor="licensePlate" className="form-label">
                    License Plate Number
                  </label>
                  <input
                    type="text"
                    className="form-control"
                    id="licensePlate"
                    name="licensePlate"
                    value={labelData.licensePlate}
                    onChange={handleInputChange}
                    placeholder="e.g., 29A-12345"
                  />
                </div>

                <div className="mb-3">
                  <label htmlFor="vehicleType" className="form-label">
                    Vehicle Type
                  </label>
                  <select
                    className="form-select"
                    id="vehicleType"
                    name="vehicleType"
                    value={labelData.vehicleType}
                    onChange={handleInputChange}
                  >
                    <option value="">Select type...</option>
                    {vehicleTypes.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="mb-3">
                  <label htmlFor="color" className="form-label">
                    Vehicle Color
                  </label>
                  <select
                    className="form-select"
                    id="color"
                    name="color"
                    value={labelData.color}
                    onChange={handleInputChange}
                  >
                    <option value="">Select color...</option>
                    {colors.map((color) => (
                      <option key={color} value={color}>
                        {color}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="d-grid gap-2">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleSave}
                  >
                    <i className="bi bi-save me-2"></i>
                    Save Label
                  </button>
                  <button
                    type="button"
                    className="btn btn-success"
                    onClick={() => {
                      handleSave();
                      handleNext();
                    }}
                  >
                    <i className="bi bi-check2 me-2"></i>
                    Save & Next
                  </button>
                </div>
              </form>
            </div>
          </div>

          <div className="card mt-3">
            <div className="card-header">
              <h5 className="mb-0">Keyboard Shortcuts</h5>
            </div>
            <div className="card-body">
              <ul className="list-unstyled mb-0 small">
                <li className="mb-2">
                  <kbd>←</kbd> Previous image
                </li>
                <li className="mb-2">
                  <kbd>→</kbd> Next image
                </li>
                <li className="mb-2">
                  <kbd>Ctrl+S</kbd> Save label
                </li>
                <li>
                  <kbd>Ctrl+Enter</kbd> Save & Next
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Labeling;
