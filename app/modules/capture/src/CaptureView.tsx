import { requireNativeView } from 'expo';
import * as React from 'react';

import { CaptureViewProps } from './Capture.types';

const NativeView: React.ComponentType<CaptureViewProps> = requireNativeView('Capture');

export default function CaptureView(props: CaptureViewProps) {
  return <NativeView {...props} />;
}
