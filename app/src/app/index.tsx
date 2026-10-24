import { CameraPreview, type CaptureReadiness } from '@capture';
import { Linking, StyleSheet, View } from 'react-native';

import { Notice } from '@/components/notice';
import { useCaptureReadiness } from '@/hooks/use-capture-readiness';

const openSettings = () => {
  void Linking.openSettings();
};

const notices: Record<Exclude<CaptureReadiness, 'ready' | 'needsPermission'>, { title: string; message: string }> = {
  cameraDenied: {
    title: 'Camera access is off',
    message: 'CaptureKit needs the back camera to record video. Turn on Camera for CaptureKit in Settings.',
  },
  motionDenied: {
    title: 'Motion access is off',
    message:
      'CaptureKit records motion-sensor data together with the video. Turn on Motion & Fitness for CaptureKit in Settings.',
  },
  noCamera: {
    title: 'No camera available',
    message: 'This device has no back camera (the iOS Simulator has none). Run CaptureKit on an iPhone to see the preview.',
  },
};

export default function CaptureScreen() {
  const { readiness, requestPermissions } = useCaptureReadiness();

  switch (readiness) {
    case 'ready':
      return (
        <View style={styles.preview}>
          <CameraPreview style={StyleSheet.absoluteFill} />
        </View>
      );
    case 'needsPermission':
      return (
        <Notice
          title="Camera and motion access"
          message="CaptureKit records video from the back camera together with motion-sensor data."
          action={{ label: 'Allow access', onPress: requestPermissions }}
        />
      );
    case 'cameraDenied':
    case 'motionDenied':
      return <Notice {...notices[readiness]} action={{ label: 'Open Settings', onPress: openSettings }} />;
    case 'noCamera':
      return <Notice {...notices.noCamera} />;
  }
}

const styles = StyleSheet.create({
  preview: { flex: 1, backgroundColor: '#000000' },
});
