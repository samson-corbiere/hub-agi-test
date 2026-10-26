import { requireNativeView } from 'expo';
import type { ComponentType } from 'react';
import type { NativeSyntheticEvent, StyleProp, ViewStyle } from 'react-native';

export type CameraErrorEvent = NativeSyntheticEvent<{ message: string }>;

export type CameraPreviewProps = {
  style?: StyleProp<ViewStyle>;
  /** The camera could not be set up, or stopped with an error. Remount the view to retry. */
  onCameraError?: (event: CameraErrorEvent) => void;
};

/** Live back-camera preview. Mount it only when readiness is `ready`. */
export const CameraPreview: ComponentType<CameraPreviewProps> = requireNativeView('Capture');
