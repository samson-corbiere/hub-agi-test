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

/** What the Capture screen shows, given the native readiness and the last camera error. */
export function captureScreen(readiness: CaptureReadiness, cameraError: string | null): CaptureScreen {
  return { kind: 'preview' };
}
