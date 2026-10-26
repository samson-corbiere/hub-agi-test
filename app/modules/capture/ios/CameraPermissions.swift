import AVFoundation

/// Shell: reads and requests the camera permission, translated into CaptureCore's
/// `CameraAccess`. The decision of what to show lives in CaptureCore.
/// Motion needs no permission: CMDeviceMotion is not gated by Motion & Fitness.
enum CameraPermissions {
  /// The back wide-angle camera, or nil when there is none (the iOS Simulator).
  static var backCamera: AVCaptureDevice? {
    AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back)
  }

  static var camera: CameraAccess {
    guard backCamera != nil else { return .unavailable }
    switch AVCaptureDevice.authorizationStatus(for: .video) {
    case .notDetermined: return .notDetermined
    case .restricted: return .restricted
    case .denied: return .denied
    case .authorized: return .authorized
    @unknown default: return .denied
    }
  }

  static func readiness() -> CaptureReadiness {
    CaptureReadiness(camera: camera)
  }

  /// Shows the system camera prompt if the user hasn't decided yet.
  static func requestIfUndecided() async {
    if camera == .notDetermined {
      _ = await AVCaptureDevice.requestAccess(for: .video)
    }
  }
}
