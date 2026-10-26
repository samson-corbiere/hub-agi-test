import { NativeModule, requireNativeModule } from 'expo';

/** What the Capture screen shows. Decided natively by CaptureCore's `CaptureReadiness`. */
export type CaptureReadiness = 'ready' | 'needsPermission' | 'cameraDenied' | 'noCamera';

declare class CaptureModule extends NativeModule<{}> {
  getReadiness(): CaptureReadiness;
  /** Prompts for the camera if not decided yet, then resolves with the new readiness. */
  requestPermissions(): Promise<CaptureReadiness>;
}

export default requireNativeModule<CaptureModule>('Capture');
