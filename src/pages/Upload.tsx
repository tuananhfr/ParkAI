import { useState } from 'react';

const Upload = () => {
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [previews, setPreviews] = useState<string[]>([]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      setSelectedFiles(files);

      // Create preview URLs
      const previewUrls: string[] = [];
      for (let i = 0; i < files.length; i++) {
        previewUrls.push(URL.createObjectURL(files[i]));
      }
      setPreviews(previewUrls);
    }
  };

  const handleUpload = () => {
    if (selectedFiles) {
      alert(`Uploading ${selectedFiles.length} file(s)... (Placeholder)`);
      // TODO: Implement actual upload logic
    }
  };

  return (
    <div>
      <h2 className="mb-4">Upload Images/Videos</h2>

      <div className="row">
        <div className="col-lg-6">
          <div className="card">
            <div className="card-header">
              <h5 className="mb-0">Select Files</h5>
            </div>
            <div className="card-body">
              <div className="mb-3">
                <label htmlFor="fileInput" className="form-label">
                  Choose images or videos
                </label>
                <input
                  type="file"
                  className="form-control"
                  id="fileInput"
                  multiple
                  accept="image/*,video/*"
                  onChange={handleFileChange}
                />
                <div className="form-text">
                  Supported formats: JPG, PNG, MP4, AVI
                </div>
              </div>

              <div className="d-grid gap-2">
                <button
                  className="btn btn-primary btn-lg"
                  onClick={handleUpload}
                  disabled={!selectedFiles}
                >
                  <i className="bi bi-cloud-upload me-2"></i>
                  Upload Files
                </button>
              </div>

              {selectedFiles && (
                <div className="alert alert-info mt-3">
                  <i className="bi bi-info-circle me-2"></i>
                  {selectedFiles.length} file(s) selected
                </div>
              )}
            </div>
          </div>

          <div className="card mt-3">
            <div className="card-header">
              <h5 className="mb-0">Upload Guidelines</h5>
            </div>
            <div className="card-body">
              <ul className="mb-0">
                <li>Maximum file size: 100MB</li>
                <li>Recommended resolution: 1920x1080 or higher</li>
                <li>Clear visibility of license plates</li>
                <li>Good lighting conditions preferred</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="col-lg-6">
          <div className="card">
            <div className="card-header">
              <h5 className="mb-0">Preview</h5>
            </div>
            <div className="card-body">
              {previews.length > 0 ? (
                <div className="row g-2">
                  {previews.map((preview, index) => (
                    <div key={index} className="col-6">
                      <div className="border rounded p-2">
                        <img
                          src={preview}
                          alt={`Preview ${index + 1}`}
                          className="img-fluid rounded"
                          style={{ maxHeight: '200px', width: '100%', objectFit: 'cover' }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-muted py-5">
                  <i className="bi bi-image fs-1 d-block mb-3"></i>
                  <p>No files selected</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Upload;
