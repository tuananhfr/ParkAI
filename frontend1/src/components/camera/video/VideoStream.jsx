import { useRef, useEffect } from "react";

/**
 * Video stream component với canvas overlay cho detections
 */
const VideoStream = ({
  videoRef,
  canvasRef,
  isVideoLoaded,
  detections,
  lastDetectionTime,
  onFullscreenToggle,
  isFullscreen,
}) => {
  const animationFrameRef = useRef(null);

  const drawDetections = () => {
    const canvas = canvasRef.current;
    const video = videoRef.current;

    if (!canvas || !video || video.videoWidth === 0) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const now = Date.now();
    if (now - lastDetectionTime > 1000) {
      //Xe ra khoi tam cam (detection timeout > 1s)
      return;
    }

    detections.forEach((detection) => {
      const [x, y, w, h] = detection.bbox;
      let label = detection.class;
      if (detection.text) {
        label = `${detection.class}: ${detection.text}`;
      }
      label += ` (${((detection.confidence || 0) * 100).toFixed(0)}%)`;

      const color = detection.text ? "#00FF00" : "#0000FF";

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      ctx.font = "bold 12px Arial";
      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = color;
      ctx.fillRect(x, y - 20, textWidth + 10, 20);

      ctx.fillStyle = "#FFFFFF";
      ctx.fillText(label, x + 5, y - 5);
    });
  };

  useEffect(() => {
    const draw = () => {
      drawDetections();
      animationFrameRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [detections, lastDetectionTime]);

  return (
    <div className="position-relative bg-black h-100">
      {!isVideoLoaded && (
        <div
          className="position-absolute top-0 start-0 w-100 h-100 d-flex flex-column align-items-center justify-content-center"
          style={{ backgroundColor: "#1a1a1a", zIndex: 10 }}
        >
          <div
            className="spinner-border text-primary mb-3"
            role="status"
            style={{ width: "3rem", height: "3rem" }}
          >
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      )}

      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-100 h-100 d-block"
        style={{
          objectFit: "contain",
          opacity: isVideoLoaded ? 1 : 0,
          transition: "opacity 0.3s ease-in-out",
        }}
      />

      <canvas
        ref={canvasRef}
        className="position-absolute top-0 start-0"
        style={{
          pointerEvents: "none",
          width: "100%",
          height: "100%",
          imageRendering: "crisp-edges",
          opacity: isVideoLoaded ? 1 : 0,
          transition: "opacity 0.3s ease-in-out",
        }}
      />

      <button
        type="button"
        className="btn btn-light btn-sm position-absolute"
        style={{ bottom: "10px", right: "10px", zIndex: 30, opacity: 0.9 }}
        onClick={onFullscreenToggle}
        title={isFullscreen ? "Thu nhỏ" : "Phóng to"}
      >
        <i
          className={`bi ${
            isFullscreen ? "bi-fullscreen-exit" : "bi-fullscreen"
          }`}
        ></i>
      </button>
    </div>
  );
};

export default VideoStream;

