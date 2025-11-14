import { Link, useLocation } from 'react-router-dom';

const Sidebar = () => {
  const location = useLocation();

  const menuItems = [
    { path: '/', icon: 'bi-speedometer2', label: 'Dashboard' },
    { path: '/upload', icon: 'bi-cloud-upload', label: 'Upload' },
    { path: '/labeling', icon: 'bi-tag', label: 'Labeling' },
    { path: '/dataset', icon: 'bi-table', label: 'Dataset' },
  ];

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div className="d-flex flex-column flex-shrink-0 p-3 bg-dark text-white" style={{ width: '250px', minHeight: '100vh' }}>
      <Link to="/" className="d-flex align-items-center mb-3 mb-md-0 me-md-auto text-white text-decoration-none">
        <span className="fs-4">ParkAI Admin</span>
      </Link>
      <hr />
      <ul className="nav nav-pills flex-column mb-auto">
        {menuItems.map((item) => (
          <li key={item.path} className="nav-item">
            <Link
              to={item.path}
              className={`nav-link ${isActive(item.path) ? 'active' : 'text-white'}`}
            >
              <i className={`bi ${item.icon} me-2`}></i>
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
      <hr />
      <div className="dropdown">
        <a
          href="#"
          className="d-flex align-items-center text-white text-decoration-none dropdown-toggle"
          data-bs-toggle="dropdown"
        >
          <i className="bi bi-person-circle me-2"></i>
          <strong>Admin User</strong>
        </a>
      </div>
    </div>
  );
};

export default Sidebar;
