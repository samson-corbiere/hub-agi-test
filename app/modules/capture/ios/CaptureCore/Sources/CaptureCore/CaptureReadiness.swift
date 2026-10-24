/// Access to one sensor (camera or motion), as reported by the platform.
/// `unavailable` means the hardware is missing (e.g. the iOS Simulator has no camera).
public enum SensorAccess: String, CaseIterable, Sendable {
    case unavailable, notDetermined, denied, restricted, authorized
}

/// What the Capture screen shows. The raw values are the strings React Native receives.
public enum CaptureReadiness: String, Sendable {
    /// Show the live camera preview.
    case ready
    /// Ask for the camera and/or motion permission.
    case needsPermission
    /// Explain why the camera is needed and offer to open Settings.
    case cameraDenied
    /// Explain why motion data is needed and offer to open Settings.
    case motionDenied
    /// There is no camera to preview (e.g. the iOS Simulator).
    case noCamera

    /// Missing hardware wins over permissions, a denied camera over a denied motion
    /// permission, and any denial over an undecided one. Missing motion hardware does
    /// not block the preview.
    public init(camera: SensorAccess, motion: SensorAccess) {
        switch (camera, motion) {
        case (.unavailable, _):
            self = .noCamera
        case (.denied, _), (.restricted, _):
            self = .cameraDenied
        case (_, .denied), (_, .restricted):
            self = .motionDenied
        case (.notDetermined, _), (_, .notDetermined):
            self = .needsPermission
        case (.authorized, .authorized), (.authorized, .unavailable):
            self = .ready
        }
    }
}
