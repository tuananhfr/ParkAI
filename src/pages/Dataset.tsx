import { useState } from 'react';

interface DatasetItem {
  id: number;
  thumbnail: string;
  licensePlate: string;
  vehicleType: string;
  color: string;
  status: 'labeled' | 'pending' | 'error';
  createdAt: string;
}

const Dataset = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');

  // Mock dataset
  const mockDataset: DatasetItem[] = [
    {
      id: 1,
      thumbnail: 'https://via.placeholder.com/100/3498db/ffffff?text=1',
      licensePlate: '29A-12345',
      vehicleType: 'Sedan',
      color: 'White',
      status: 'labeled',
      createdAt: '2024-01-15 10:30',
    },
    {
      id: 2,
      thumbnail: 'https://via.placeholder.com/100/e74c3c/ffffff?text=2',
      licensePlate: '30B-67890',
      vehicleType: 'SUV',
      color: 'Black',
      status: 'labeled',
      createdAt: '2024-01-15 10:25',
    },
    {
      id: 3,
      thumbnail: 'https://via.placeholder.com/100/f39c12/ffffff?text=3',
      licensePlate: 'N/A',
      vehicleType: 'Truck',
      color: 'Red',
      status: 'pending',
      createdAt: '2024-01-15 10:20',
    },
    {
      id: 4,
      thumbnail: 'https://via.placeholder.com/100/95a5a6/ffffff?text=4',
      licensePlate: 'N/A',
      vehicleType: 'N/A',
      color: 'N/A',
      status: 'error',
      createdAt: '2024-01-15 10:15',
    },
  ];

  const getStatusBadge = (status: string) => {
    const badges = {
      labeled: 'bg-success',
      pending: 'bg-warning',
      error: 'bg-danger',
    };
    return badges[status as keyof typeof badges] || 'bg-secondary';
  };

  const handleEdit = (id: number) => {
    alert(`Editing item ${id} (Placeholder)`);
    // TODO: Navigate to labeling page with item ID
  };

  const handleDelete = (id: number) => {
    if (confirm(`Are you sure you want to delete item ${id}?`)) {
      alert(`Deleting item ${id} (Placeholder)`);
      // TODO: Implement delete logic
    }
  };

  return (
    <div>
      <h2 className="mb-4">Dataset Management</h2>

      <div className="card mb-4">
        <div className="card-body">
          <div className="row g-3">
            <div className="col-md-6">
              <div className="input-group">
                <span className="input-group-text">
                  <i className="bi bi-search"></i>
                </span>
                <input
                  type="text"
                  className="form-control"
                  placeholder="Search by license plate..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
            <div className="col-md-3">
              <select
                className="form-select"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <option value="all">All Status</option>
                <option value="labeled">Labeled</option>
                <option value="pending">Pending</option>
                <option value="error">Error</option>
              </select>
            </div>
            <div className="col-md-3">
              <button className="btn btn-primary w-100">
                <i className="bi bi-download me-2"></i>
                Export Dataset
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Dataset Items</h5>
          <span className="badge bg-secondary">{mockDataset.length} items</span>
        </div>
        <div className="card-body">
          <div className="table-responsive">
            <table className="table table-hover align-middle">
              <thead>
                <tr>
                  <th style={{ width: '100px' }}>Thumbnail</th>
                  <th>License Plate</th>
                  <th>Vehicle Type</th>
                  <th>Color</th>
                  <th>Status</th>
                  <th>Created At</th>
                  <th style={{ width: '150px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {mockDataset.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <img
                        src={item.thumbnail}
                        alt={`Item ${item.id}`}
                        className="img-thumbnail"
                        style={{ width: '80px', height: '60px', objectFit: 'cover' }}
                      />
                    </td>
                    <td>
                      <strong>{item.licensePlate}</strong>
                    </td>
                    <td>{item.vehicleType}</td>
                    <td>{item.color}</td>
                    <td>
                      <span className={`badge ${getStatusBadge(item.status)}`}>
                        {item.status}
                      </span>
                    </td>
                    <td className="text-muted small">{item.createdAt}</td>
                    <td>
                      <div className="btn-group btn-group-sm" role="group">
                        <button
                          className="btn btn-outline-primary"
                          onClick={() => handleEdit(item.id)}
                          title="Edit"
                        >
                          <i className="bi bi-pencil"></i>
                        </button>
                        <button
                          className="btn btn-outline-danger"
                          onClick={() => handleDelete(item.id)}
                          title="Delete"
                        >
                          <i className="bi bi-trash"></i>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <nav className="mt-3">
            <ul className="pagination justify-content-center mb-0">
              <li className="page-item disabled">
                <a className="page-link" href="#">Previous</a>
              </li>
              <li className="page-item active">
                <a className="page-link" href="#">1</a>
              </li>
              <li className="page-item">
                <a className="page-link" href="#">2</a>
              </li>
              <li className="page-item">
                <a className="page-link" href="#">3</a>
              </li>
              <li className="page-item">
                <a className="page-link" href="#">Next</a>
              </li>
            </ul>
          </nav>
        </div>
      </div>
    </div>
  );
};

export default Dataset;
