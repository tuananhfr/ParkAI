export type CameraType = 'rtsp' | 'public';

export interface Camera {
  id: string;
  name: string;
  type: CameraType;
  url: string;
  enabled?: boolean;
}

export interface Go2RTCStream {
  producers?: Array<{
    url: string;
    [key: string]: any;
  }>;
  consumers?: any;
  [key: string]: any;
}
