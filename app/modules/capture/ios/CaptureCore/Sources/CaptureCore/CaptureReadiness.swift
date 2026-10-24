/// Access to one sensor (camera or motion), as reported by the platform.
public enum SensorAccess: String, CaseIterable, Sendable {
    case unavailable, notDetermined, denied, restricted, authorized
}

/// What the Capture screen shows.
public enum CaptureReadiness: String, Sendable {
    case ready, needsPermission, cameraDenied, motionDenied, noCamera

    public init(camera: SensorAccess, motion: SensorAccess) {
        self = .ready
    }
}
