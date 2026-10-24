import XCTest
import CaptureCore

/// What the Capture screen shows, given camera and motion access.
final class CaptureReadinessTests: XCTestCase {
    private func readiness(camera: SensorAccess, motion: SensorAccess) -> CaptureReadiness {
        CaptureReadiness(camera: camera, motion: motion)
    }

    func testBothAuthorizedShowsThePreview() {
        XCTAssertEqual(readiness(camera: .authorized, motion: .authorized), .ready)
    }

    func testMotionUnavailableDoesNotBlockThePreview() {
        XCTAssertEqual(readiness(camera: .authorized, motion: .unavailable), .ready)
    }

    func testNoCameraHardwareShowsNoCameraWhateverTheMotionAccess() {
        for motion in SensorAccess.allCases {
            XCTAssertEqual(readiness(camera: .unavailable, motion: motion), .noCamera, "motion: \(motion)")
        }
    }

    func testDeniedOrRestrictedCameraShowsCameraDenied() {
        for camera in [SensorAccess.denied, .restricted] {
            for motion in SensorAccess.allCases {
                XCTAssertEqual(readiness(camera: camera, motion: motion), .cameraDenied, "camera: \(camera), motion: \(motion)")
            }
        }
    }

    func testDeniedOrRestrictedMotionShowsMotionDenied() {
        for camera in [SensorAccess.authorized, .notDetermined] {
            for motion in [SensorAccess.denied, .restricted] {
                XCTAssertEqual(readiness(camera: camera, motion: motion), .motionDenied, "camera: \(camera), motion: \(motion)")
            }
        }
    }

    func testUndecidedAccessNeedsPermission() {
        XCTAssertEqual(readiness(camera: .notDetermined, motion: .authorized), .needsPermission)
        XCTAssertEqual(readiness(camera: .notDetermined, motion: .unavailable), .needsPermission)
        XCTAssertEqual(readiness(camera: .authorized, motion: .notDetermined), .needsPermission)
        XCTAssertEqual(readiness(camera: .notDetermined, motion: .notDetermined), .needsPermission)
    }

    func testRawValuesAreTheStringsReactNativeReceives() {
        XCTAssertEqual(CaptureReadiness.ready.rawValue, "ready")
        XCTAssertEqual(CaptureReadiness.needsPermission.rawValue, "needsPermission")
        XCTAssertEqual(CaptureReadiness.cameraDenied.rawValue, "cameraDenied")
        XCTAssertEqual(CaptureReadiness.motionDenied.rawValue, "motionDenied")
        XCTAssertEqual(CaptureReadiness.noCamera.rawValue, "noCamera")
    }
}
