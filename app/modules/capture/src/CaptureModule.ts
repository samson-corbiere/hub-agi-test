import { NativeModule, requireNativeModule } from 'expo';

declare class CaptureModule extends NativeModule<{}> {
  hello(): string;
}

export default requireNativeModule<CaptureModule>('Capture');
