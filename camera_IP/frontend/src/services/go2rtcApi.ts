import type { Camera, Go2RTCStream } from '../types/camera';

const GO2RTC_API_URL = 'http://localhost:1984';

export class Go2RTCApi {
  private baseUrl: string;

  constructor(baseUrl: string = GO2RTC_API_URL) {
    this.baseUrl = baseUrl;
  }

  // Get all streams
  async getStreams(): Promise<Record<string, Go2RTCStream>> {
    const response = await fetch(`${this.baseUrl}/api/streams`);
    if (!response.ok) {
      throw new Error('Failed to fetch streams');
    }
    return response.json();
  }

  // Add a new stream
  async addStream(camera: Camera): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/config`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        streams: {
          [camera.id]: camera.url,
        },
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to add stream: ${errorText}`);
    }
  }

  // Remove a stream
  async removeStream(streamId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/config`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        streams: {
          [streamId]: null,
        },
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to remove stream: ${errorText}`);
    }
  }

  // Get WebRTC stream URL for a camera (using dynamic stream with RTSP URL)
  getStreamUrl(cameraUrl: string): string {
    return `${this.baseUrl}/api/ws?src=${encodeURIComponent(cameraUrl)}`;
  }

  // Get preview image URL
  getSnapshotUrl(cameraId: string): string {
    return `${this.baseUrl}/api/frame.jpeg?src=${cameraId}`;
  }
}

export const go2rtcApi = new Go2RTCApi();
