import AVFoundation
import CoreMotion

/// Shell: reads and requests camera and motion permissions from the platform, translated
/// into CaptureCore's `SensorAccess`. The decision of what to show lives in CaptureCore.
enum SensorPermissions {
  /// The back wide-angle camera, or nil when there is none (the iOS Simulator).
  static var backCamera: AVCaptureDevice? {
    AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back)
  }

  static var camera: SensorAccess {
    guard backCamera != nil else { return .unavailable }
    switch AVCaptureDevice.authorizationStatus(for: .video) {
    case .notDetermined: return .notDetermined
    case .restricted: return .restricted
    case .denied: return .denied
    case .authorized: return .authorized
    @unknown default: return .denied
    }
  }

  /// The "Motion & Fitness" permission (NSMotionUsageDescription).
  static var motion: SensorAccess {
    guard CMMotionActivityManager.isActivityAvailable() else { return .unavailable }
    switch CMMotionActivityManager.authorizationStatus() {
    case .notDetermined: return .notDetermined
    case .restricted: return .restricted
    case .denied: return .denied
    case .authorized: return .authorized
    @unknown default: return .denied
    }
  }

  static func readiness() -> CaptureReadiness {
    CaptureReadiness(camera: camera, motion: motion)
  }

  /// Shows the system prompt for each permission not decided yet, one after the other.
  static func requestUndecided() async {
    if camera == .notDetermined {
      _ = await AVCaptureDevice.requestAccess(for: .video)
    }
    if motion == .notDetermined {
      await requestMotion()
    }
  }

  /// CoreMotion has no explicit request call: the first activity query shows the prompt.
  private static func requestMotion() async {
    let manager = CMMotionActivityManager()
    await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
      let now = Date()
      manager.queryActivityStarting(from: now, to: now, to: .main) { _, _ in
        continuation.resume()
      }
    }
    withExtendedLifetime(manager) {}
  }
}
