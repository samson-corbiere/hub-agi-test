import { Capture, type CaptureReadiness } from '@capture';
import { useEffect, useState } from 'react';
import { AppState } from 'react-native';

/**
 * Current CaptureReadiness. Prompts for undecided permissions once, and re-reads the
 * state whenever the app comes back to the foreground (e.g. from the Settings app).
 */
export function useCaptureReadiness(): {
  readiness: CaptureReadiness;
  requestPermissions: () => void;
} {
  const [readiness, setReadiness] = useState<CaptureReadiness>(() => Capture.getReadiness());

  const requestPermissions = () => {
    Capture.requestPermissions().then(setReadiness, () => setReadiness(Capture.getReadiness()));
  };

  useEffect(() => {
    if (Capture.getReadiness() === 'needsPermission') {
      requestPermissions();
    }
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        setReadiness(Capture.getReadiness());
      }
    });
    return () => subscription.remove();
  }, []);

  return { readiness, requestPermissions };
}
