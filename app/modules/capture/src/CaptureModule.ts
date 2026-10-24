import { NativeModule, requireNativeModule } from 'expo';

/** What the Capture screen shows. Decided natively by CaptureCore's `CaptureReadiness`. */
export type CaptureReadiness =
  | 'ready'
  | 'needsPermission'
  | 'cameraDenied'
  | 'motionDenied'
  | 'noCamera';

declare class CaptureModule extends NativeModule<{}> {
  getReadiness(): CaptureReadiness;
  requestPermissions(): Promise<CaptureReadiness>;
}

export default requireNativeModule<CaptureModule>('Capture');
