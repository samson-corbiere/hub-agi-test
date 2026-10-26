import { CameraPreview } from '@capture';
import { useEffect, useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';

import { Notice } from '@/components/notice';
import { useCaptureReadiness } from '@/hooks/use-capture-readiness';
import { captureScreen, type NoticeIntent } from '@/lib/capture-screen';

export default function CaptureScreen() {
  const { readiness, requestPermissions } = useCaptureReadiness();
  const [cameraError, setCameraError] = useState<string | null>(null);
  // A new key remounts the native view, which sets the camera up again.
  const [previewKey, setPreviewKey] = useState(0);

  useEffect(() => {
    if (readiness !== 'ready') {
      setCameraError(null);
    }
  }, [readiness]);

  const actions: Record<NoticeIntent, () => void> = {
    requestPermission: requestPermissions,
    openSettings: () => void Linking.openSettings(),
    retryCamera: () => {
      setCameraError(null);
      setPreviewKey((key) => key + 1);
    },
  };

  const screen = captureScreen(readiness, cameraError);
  if (screen.kind === 'preview') {
    return (
      <View style={styles.preview}>
        <CameraPreview
          key={previewKey}
          style={StyleSheet.absoluteFill}
          onCameraError={(event) => setCameraError(event.nativeEvent.message)}
        />
      </View>
    );
  }
  const { action } = screen;
  return (
    <Notice
      title={screen.title}
      message={screen.message}
      action={action && { label: action.label, onPress: actions[action.intent] }}
    />
  );
}

const styles = StyleSheet.create({
  preview: { flex: 1, backgroundColor: '#000000' },
});
