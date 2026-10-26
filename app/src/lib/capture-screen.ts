import type { CaptureReadiness } from '@capture';

export type NoticeIntent = 'requestPermission' | 'openSettings' | 'retryCamera';

export type CaptureScreen =
  | { kind: 'preview' }
  | {
      kind: 'notice';
      title: string;
      message: string;
      action?: { label: string; intent: NoticeIntent };
    };

/**
 * What the Capture screen shows, given the native readiness and the last error the
 * preview reported (null if none). The error only matters while the camera is ready.
 */
export function captureScreen(readiness: CaptureReadiness, cameraError: string | null): CaptureScreen {
  switch (readiness) {
    case 'ready':
      if (cameraError === null) {
        return { kind: 'preview' };
      }
      return {
        kind: 'notice',
        title: "The camera couldn't start",
        message: cameraError,
        action: { label: 'Try again', intent: 'retryCamera' },
      };
    case 'needsPermission':
      return {
        kind: 'notice',
        title: 'Camera access',
        message: 'CaptureKit records video from the back camera, together with motion-sensor data.',
        action: { label: 'Allow camera access', intent: 'requestPermission' },
      };
    case 'cameraDenied':
      return {
        kind: 'notice',
        title: 'Camera access is off',
        message: 'CaptureKit needs the back camera to record video. Turn on Camera for CaptureKit in Settings.',
        action: { label: 'Open Settings', intent: 'openSettings' },
      };
    case 'noCamera':
      return {
        kind: 'notice',
        title: 'No camera available',
        message:
          'This device has no back camera (the iOS Simulator has none). Run CaptureKit on an iPhone to see the preview.',
      };
  }
}
