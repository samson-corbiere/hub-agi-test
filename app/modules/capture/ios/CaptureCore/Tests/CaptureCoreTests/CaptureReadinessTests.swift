import XCTest
import CaptureCore

/// What the Capture screen shows, given camera access. Motion needs no permission
/// (CMDeviceMotion is not gated by Motion & Fitness), so it never blocks the preview.
final class CaptureReadinessTests: XCTestCase {
    func testAuthorizedCameraShowsThePreview() {
        XCTAssertEqual(CaptureReadiness(camera: .authorized), .ready)
    }

    func testNoCameraHardwareShowsNoCamera() {
        XCTAssertEqual(CaptureReadiness(camera: .unavailable), .noCamera)
    }

    func testDeniedOrRestrictedCameraShowsCameraDenied() {
        XCTAssertEqual(CaptureReadiness(camera: .denied), .cameraDenied)
        XCTAssertEqual(CaptureReadiness(camera: .restricted), .cameraDenied)
    }

    func testUndecidedCameraNeedsPermission() {
        XCTAssertEqual(CaptureReadiness(camera: .notDetermined), .needsPermission)
    }

    func testRawValuesAreTheStringsReactNativeReceives() {
        XCTAssertEqual(
            CaptureReadiness.allCases.map(\.rawValue).sorted(),
            ["cameraDenied", "needsPermission", "noCamera", "ready"]
        )
    }
}
