const Dashboard = () => {
  const stats = [
    { title: 'Total Uploads', value: '1,234', icon: 'bi-cloud-upload', color: 'primary' },
    { title: 'Labeled', value: '856', icon: 'bi-check-circle', color: 'success' },
    { title: 'Pending', value: '378', icon: 'bi-clock', color: 'warning' },
    { title: 'AI Errors', value: '12', icon: 'bi-exclamation-triangle', color: 'danger' },
  ];

  return (
    <div>
      <h2 className="mb-4">Dashboard</h2>

      <div className="row g-4">
        {stats.map((stat, index) => (
          <div key={index} className="col-md-6 col-lg-3">
            <div className="card">
              <div className="card-body">
                <div className="d-flex justify-content-between align-items-center">
                  <div>
                    <p className="text-muted mb-1">{stat.title}</p>
                    <h3 className="mb-0">{stat.value}</h3>
                  </div>
                  <div className={`bg-${stat.color} bg-opacity-10 p-3 rounded`}>
                    <i className={`bi ${stat.icon} fs-2 text-${stat.color}`}></i>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="row mt-4">
        <div className="col-lg-8">
          <div className="card">
            <div className="card-header">
              <h5 className="mb-0">Recent Activity</h5>
            </div>
            <div className="card-body">
              <div className="table-responsive">
                <table className="table table-hover">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Action</th>
                      <th>File</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>2024-01-15 10:30</td>
                      <td>Upload</td>
                      <td>IMG_001.jpg</td>
                      <td><span className="badge bg-success">Success</span></td>
                    </tr>
                    <tr>
                      <td>2024-01-15 10:25</td>
                      <td>Label</td>
                      <td>IMG_002.jpg</td>
                      <td><span className="badge bg-success">Success</span></td>
                    </tr>
                    <tr>
                      <td>2024-01-15 10:20</td>
                      <td>Upload</td>
                      <td>VID_001.mp4</td>
                      <td><span className="badge bg-warning">Processing</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <div className="col-lg-4">
          <div className="card">
            <div className="card-header">
              <h5 className="mb-0">Quick Stats</h5>
            </div>
            <div className="card-body">
              <div className="mb-3">
                <div className="d-flex justify-content-between mb-1">
                  <span>Completion Rate</span>
                  <span className="fw-bold">69%</span>
                </div>
                <div className="progress">
                  <div className="progress-bar bg-success" style={{ width: '69%' }}></div>
                </div>
              </div>
              <div className="mb-3">
                <div className="d-flex justify-content-between mb-1">
                  <span>Error Rate</span>
                  <span className="fw-bold">1%</span>
                </div>
                <div className="progress">
                  <div className="progress-bar bg-danger" style={{ width: '1%' }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
