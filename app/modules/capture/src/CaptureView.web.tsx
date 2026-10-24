import { CaptureViewProps } from './Capture.types';

// CaptureView is not available on the web platform.
export default function CaptureView(_props: CaptureViewProps) {
  throw new Error('CaptureView is not available on the web platform.');
}
