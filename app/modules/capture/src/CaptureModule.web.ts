import { registerWebModule, NativeModule } from 'expo';

// CaptureModule is not available on the web platform.
class CaptureModule extends NativeModule<{}> {}

export default registerWebModule(CaptureModule, 'CaptureModule');
