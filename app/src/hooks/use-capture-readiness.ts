import { Capture, type CaptureReadiness } from '@capture';
import { useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';

/**
 * Current CaptureReadiness. Prompts for an undecided camera permission once, and re-reads
 * the state whenever the app comes back to the foreground (e.g. from the Settings app).
 */
export function useCaptureReadiness(): {
  readiness: CaptureReadiness;
  requestPermissions: () => void;
} {
  const [readiness, setReadiness] = useState<CaptureReadiness>(() => Capture.getReadiness());
  const mounted = useRef(false);

  const requestPermissions = () => {
    Capture.requestPermissions()
      .catch(() => Capture.getReadiness())
      .then((next) => {
        if (mounted.current) {
          setReadiness(next);
        }
      });
  };

  useEffect(() => {
    mounted.current = true;
    if (Capture.getReadiness() === 'needsPermission') {
      requestPermissions();
    }
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        setReadiness(Capture.getReadiness());
      }
    });
    return () => {
      mounted.current = false;
      subscription.remove();
    };
  }, []);

  return { readiness, requestPermissions };
}
