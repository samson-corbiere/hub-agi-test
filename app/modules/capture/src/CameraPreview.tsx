import { requireNativeView } from 'expo';
import type { ComponentType } from 'react';
import type { StyleProp, ViewStyle } from 'react-native';

export type CameraPreviewProps = {
  style?: StyleProp<ViewStyle>;
};

/** Live back-camera preview. Mount it only when readiness is `ready`. */
export const CameraPreview: ComponentType<CameraPreviewProps> = requireNativeView('Capture');
