import XCTest
@testable import CaptureCore

final class CaptureCoreTests: XCTestCase {
    func testPackageBuilds() {
        XCTAssertFalse(CaptureCore.version.isEmpty)
    }
}
