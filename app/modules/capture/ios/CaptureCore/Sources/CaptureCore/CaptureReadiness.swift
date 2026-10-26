/// Access to the camera, as reported by the platform.
/// `unavailable` means the hardware is missing (e.g. the iOS Simulator has no camera).
public enum CameraAccess: String, CaseIterable, Sendable {
    case unavailable, notDetermined, denied, restricted, authorized
}

/// What the Capture screen shows. The raw values are the strings React Native receives.
/// Motion is not part of it: CMDeviceMotion needs no user authorization.
public enum CaptureReadiness: String, CaseIterable, Sendable {
    /// Show the live camera preview.
    case ready
    /// Ask for the camera permission.
    case needsPermission
    /// Explain why the camera is needed and offer to open Settings.
    case cameraDenied
    /// There is no camera to preview (e.g. the iOS Simulator).
    case noCamera

    public init(camera: CameraAccess) {
        switch camera {
        case .unavailable: self = .noCamera
        case .denied, .restricted: self = .cameraDenied
        case .notDetermined: self = .needsPermission
        case .authorized: self = .ready
        }
    }
}
