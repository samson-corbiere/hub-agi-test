// swift-tools-version: 6.0
import PackageDescription

// Pure Swift core of the capture module: no Expo, UIKit or AVFoundation.
// Everything here is testable with `swift test` on the Mac.
let package = Package(
    name: "CaptureCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "CaptureCore", targets: ["CaptureCore"]),
    ],
    targets: [
        .target(name: "CaptureCore"),
        .testTarget(name: "CaptureCoreTests", dependencies: ["CaptureCore"]),
    ]
)
