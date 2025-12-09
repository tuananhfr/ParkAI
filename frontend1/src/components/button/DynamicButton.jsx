const DynamicButton = ({
  icon,
  text,
  onClick,
  size = "sm",
  variant,
  className,
}) => {
  return (
    <button
      className={`btn btn-${variant} btn-${size} ${className}`}
      onClick={onClick}
    >
      {icon && <i className={`bi ${icon} me-1`}></i>}
      {text}
    </button>
  );
};

export default DynamicButton;
