import { describe, expect, it } from '@jest/globals';

import { captureScreen } from './capture-screen';

describe('captureScreen', () => {
  it('shows the preview when the camera is ready and has not failed', () => {
    expect(captureScreen('ready', null)).toEqual({ kind: 'preview' });
  });

  it('offers to retry when the camera failed to start, with the native message', () => {
    const screen = captureScreen('ready', 'The camera is in use by another app.');
    expect(screen).toMatchObject({ kind: 'notice', action: { intent: 'retryCamera' } });
    expect(screen.kind === 'notice' && screen.message).toContain('The camera is in use by another app.');
  });

  it('offers to open Settings when the camera permission is denied', () => {
    expect(captureScreen('cameraDenied', null)).toMatchObject({
      kind: 'notice',
      action: { label: 'Open Settings', intent: 'openSettings' },
    });
  });

  it('offers to ask for the permission when it is undecided', () => {
    expect(captureScreen('needsPermission', null)).toMatchObject({
      kind: 'notice',
      action: { intent: 'requestPermission' },
    });
  });

  it('explains that there is no camera, with nothing to do about it', () => {
    const screen = captureScreen('noCamera', null);
    expect(screen).toMatchObject({ kind: 'notice', title: 'No camera available' });
    expect(screen.kind === 'notice' && screen.action).toBeUndefined();
  });

  it('ignores a stale camera error once the camera is no longer ready', () => {
    expect(captureScreen('cameraDenied', 'old failure')).toEqual(captureScreen('cameraDenied', null));
  });
});
