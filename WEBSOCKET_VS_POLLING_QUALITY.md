# 📹 So sánh Chất lượng Video: WebRTC vs Polling

## 🔍 Phân tích Hiện tại

### **Kiến trúc hiện tại:**

1. **Video Stream**: WebRTC (RTCPeerConnection) ✅
   - Real-time, low latency
   - Adaptive bitrate (tự động điều chỉnh chất lượng)
   - Có thể bị giảm chất lượng khi network yếu

2. **WebSocket**: Chỉ cho detections data (JSON) ✅
   - Không ảnh hưởng đến video quality
   - Dùng cho real-time updates

3. **Polling**: Không có ❌
   - Không dùng polling cho images/video

---

## ⚠️ Vấn đề: WebRTC có thể bị giảm chất lượng

### **Nguyên nhân:**

1. **Adaptive Bitrate (ABR)**
   - WebRTC tự động giảm bitrate khi network yếu
   - Browser tự điều chỉnh resolution/fps
   - Không có codec/bitrate constraints

2. **Thiếu Configuration**
   - Không set codec preferences (H.264, VP8, VP9)
   - Không set bitrate limits
   - Không set resolution constraints

3. **Network Conditions**
   - Latency cao → giảm quality
   - Packet loss → giảm quality
   - Bandwidth thấp → giảm quality

---

## 📊 So sánh: WebRTC vs Polling Images

### **WebRTC (hiện tại):**
```
✅ Real-time (low latency ~100-200ms)
✅ Smooth playback (30fps)
❌ Có thể bị adaptive bitrate
❌ Phụ thuộc network conditions
❌ Compression loss
```

### **Polling Images (JPEG snapshots):**
```
✅ Chất lượng tốt hơn (full resolution, no compression loss)
✅ Ổn định (không bị adaptive)
❌ High latency (1-5 giây delay)
❌ Không smooth (stuttering)
❌ Tốn bandwidth hơn (nhiều requests)
```

---

## 🎯 Giải pháp: Tối ưu WebRTC Quality

### **1. Set Codec Preferences & Constraints**

#### **Backend (Edge):**

```python
# backend-edge1/app.py
from aiortc import RTCRtpCodecCapability

@app.post("/offer")
async def webrtc_offer(request: Request):
    # ... existing code ...
    
    pc = RTCPeerConnection(
        rtcConfiguration=RTCConfiguration(
            # Prefer H.264 codec (better quality)
            codecs=[
                RTCRtpCodecCapability(
                    mimeType="video/H264",
                    clockRate=90000,
                    channels=None,
                ),
                RTCRtpCodecCapability(
                    mimeType="video/VP8",
                    clockRate=90000,
                    channels=None,
                ),
            ]
        )
    )
    
    # Set video encoding parameters
    camera_track = CameraVideoTrack(camera_manager)
    
    # Configure transceiver with constraints
    transceiver = pc.addTransceiver(
        camera_track,
        direction="sendonly",
        init=RTCRtpTransceiverInit(
            direction="sendonly",
            streams=[pc.createLocalStream("camera")]
        )
    )
    
    # Set encoding parameters for better quality
    if transceiver.sender:
        params = transceiver.sender.getParameters()
        params.encodings[0].maxBitrate = 2500000  # 2.5 Mbps
        params.encodings[0].maxFramerate = 30
        params.encodings[0].scaleResolutionDownBy = 1.0  # No downscaling
        await transceiver.sender.setParameters(params)
```

#### **Frontend:**

```javascript
// frontend/src/components/CameraView.jsx
const pc = new RTCPeerConnection({
  iceServers: [{ urls: ["stun:stun.l.google.com:19302"] }],
});

// Add transceiver với constraints
const transceiver = pc.addTransceiver("video", {
  direction: "recvonly",
});

// Set receiver constraints for better quality
transceiver.receiver.track.getSettings();
transceiver.receiver.track.getCapabilities();

// Set preferred codec
await pc.setConfiguration({
  sdpSemantics: 'unified-plan',
  codecs: [
    { kind: 'video', mimeType: 'video/H264', preferredPayloadType: 96 },
    { kind: 'video', mimeType: 'video/VP8', preferredPayloadType: 97 },
  ]
});

// Configure video quality constraints
const offer = await pc.createOffer({
  offerToReceiveVideo: true,
  offerToReceiveAudio: false,
});

// Modify SDP to prefer H.264 and set bitrate
offer.sdp = offer.sdp.replace(
  /(a=fmtp:\d+.*)/,
  '$1\r\na=x-google-max-bitrate=2500000\r\na=x-google-min-bitrate=1000000'
);
```

### **2. Set Video Encoding Parameters**

```python
# backend-edge1/app.py
class CameraVideoTrack(VideoStreamTrack):
    def __init__(self, camera_manager):
        super().__init__()
        self.camera_manager = camera_manager
        self.frame_count = 0
        
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self.camera_manager.get_raw_frame()
        
        if frame is None or frame.size == 0:
            frame = np.zeros(
                (config.RESOLUTION_HEIGHT, config.RESOLUTION_WIDTH, 3),
                dtype=np.uint8
            )
        else:
            self.frame_count += 1
            frame = frame[:, :, ::-1]  # RGB to BGR
        
        new_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        
        # Set frame metadata for better encoding
        new_frame.width = config.RESOLUTION_WIDTH
        new_frame.height = config.RESOLUTION_HEIGHT
        
        return new_frame
```

### **3. Configure SDP Parameters**

```python
# backend-edge1/app.py
async def webrtc_offer(request: Request):
    # ... existing code ...
    
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    
    # Modify SDP to set codec and bitrate
    sdp = answer.sdp
    
    # Prefer H.264
    if "H264" in sdp:
        # Set H.264 profile and level
        sdp = sdp.replace(
            "a=fmtp:96",
            "a=fmtp:96 profile-level-id=42e01f;max-mbps=108000;max-fs=3600"
        )
    
    # Set bitrate constraints
    if "a=mid:video" in sdp:
        sdp = sdp.replace(
            "a=mid:video",
            "a=mid:video\r\nb=AS:2500\r\nb=TIAS:2500000"
        )
    
    answer = RTCSessionDescription(sdp=sdp, type=answer.type)
    await pc.setLocalDescription(answer)
    
    return JSONResponse({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })
```

### **4. Add Bitrate Constraints trong Frontend**

```javascript
// frontend/src/components/CameraView.jsx
pc.ontrack = (event) => {
  const [stream] = event.streams;
  const videoTrack = stream.getVideoTracks()[0];
  
  // Get and log video settings
  const settings = videoTrack.getSettings();
  console.log('Video settings:', settings);
  
  // Apply constraints for better quality
  videoTrack.applyConstraints({
    width: { ideal: 1280 },
    height: { ideal: 720 },
    frameRate: { ideal: 30 },
    aspectRatio: { ideal: 16/9 }
  });
  
  videoRef.current.srcObject = stream;
  setIsConnected(true);
};
```

---

## 🔧 Implementation: Tối ưu WebRTC Quality

### **Option 1: Cải thiện WebRTC (Khuyến nghị)**

**Ưu điểm:**
- ✅ Giữ được real-time
- ✅ Smooth playback
- ✅ Có thể cải thiện quality với constraints

**Cách làm:**
1. Set codec preferences (H.264)
2. Set bitrate limits (2-3 Mbps)
3. Set resolution constraints (720p, 30fps)
4. Disable adaptive bitrate (nếu cần)

### **Option 2: Hybrid Approach**

**Kết hợp WebRTC + Snapshot endpoint:**

```python
# backend-edge1/app.py
@app.get("/api/snapshot")
async def get_snapshot():
    """Get high-quality snapshot (JPEG)"""
    frame = camera_manager.get_raw_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="Camera not ready")
    
    # Convert to JPEG with high quality
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return Response(content=buffer.tobytes(), media_type="image/jpeg")
```

```javascript
// Frontend: Option to switch between WebRTC and snapshot
const [useSnapshot, setUseSnapshot] = useState(false);

useEffect(() => {
  if (useSnapshot) {
    // Polling mode - fetch snapshot every 100ms
    const interval = setInterval(async () => {
      const response = await fetch(`${edgeUrl}/api/snapshot`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      imgRef.current.src = url;
    }, 100);
    return () => clearInterval(interval);
  } else {
    // WebRTC mode
    startStream();
  }
}, [useSnapshot]);
```

### **Option 3: Dual Stream (High Quality + Low Latency)**

```python
# Backend: 2 streams
# - Stream 1: High quality (lower fps, higher bitrate)
# - Stream 2: Low latency (lower quality, higher fps)

class HighQualityVideoTrack(VideoStreamTrack):
    """High quality stream - 1080p, 15fps, 5Mbps"""
    async def recv(self):
        # ... với settings cao hơn

class LowLatencyVideoTrack(VideoStreamTrack):
    """Low latency stream - 720p, 30fps, 2Mbps"""
    async def recv(self):
        # ... với settings tối ưu latency
```

---

## 📋 Checklist: Cải thiện Video Quality

### **Immediate (1-2 giờ):**

- [ ] Set codec preferences (H.264)
- [ ] Set bitrate constraints (2-3 Mbps)
- [ ] Set resolution constraints (720p)
- [ ] Test với network conditions khác nhau

### **Short-term (1 tuần):**

- [ ] Add snapshot endpoint (backup)
- [ ] Add quality selector UI
- [ ] Monitor bitrate/quality metrics
- [ ] Optimize encoding parameters

### **Long-term (1 tháng):**

- [ ] Implement dual stream (quality + latency)
- [ ] Add adaptive quality UI controls
- [ ] Network-aware quality adjustment
- [ ] Performance monitoring dashboard

---

## 🎯 Kết luận

**WebRTC tốt hơn Polling cho video streaming**, nhưng cần:

1. ✅ **Set constraints** để tránh adaptive bitrate
2. ✅ **Prefer H.264 codec** (better quality)
3. ✅ **Set bitrate limits** (2-3 Mbps cho 720p)
4. ✅ **Monitor quality** và adjust

**Polling chỉ tốt hơn nếu:**
- Cần snapshot quality (100% original)
- Không cần real-time
- Network rất yếu (WebRTC không hoạt động)

**Khuyến nghị:**
- Cải thiện WebRTC với constraints
- Thêm snapshot endpoint như backup
- Let user choose quality mode

---

## 🚀 Quick Fix: Set WebRTC Constraints

Tôi có thể giúp implement ngay:
1. Set codec preferences
2. Set bitrate constraints  
3. Add quality controls

Bạn muốn tôi bắt đầu với phần nào?

