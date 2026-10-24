import AVFoundation
import ExpoModulesCore

/// Shell: live preview of the back wide-angle camera. React Native mounts it only when
/// CaptureReadiness is `ready`. The session runs while the view is in a window.
class CameraPreviewView: ExpoView {
  private let session = AVCaptureSession()
  private let sessionQueue = DispatchQueue(label: "capturekit.preview.session")
  private let previewLayer: AVCaptureVideoPreviewLayer
  private var isConfigured = false  // only touched on sessionQueue

  required init(appContext: AppContext? = nil) {
    previewLayer = AVCaptureVideoPreviewLayer(session: session)
    super.init(appContext: appContext)
    clipsToBounds = true
    backgroundColor = .black
    previewLayer.videoGravity = .resizeAspectFill
    layer.addSublayer(previewLayer)
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    previewLayer.frame = bounds
  }

  override func didMoveToWindow() {
    super.didMoveToWindow()
    if window != nil {
      sessionQueue.async { [weak self] in self?.start() }
    } else {
      sessionQueue.async { [session] in session.stopRunning() }
    }
  }

  private func start() {
    if !isConfigured {
      isConfigured = true
      configure()
    }
    session.startRunning()
  }

  private func configure() {
    guard let camera = SensorPermissions.backCamera,
          let input = try? AVCaptureDeviceInput(device: camera) else { return }
    session.beginConfiguration()
    session.sessionPreset = .high
    if session.canAddInput(input) { session.addInput(input) }
    session.commitConfiguration()
    DispatchQueue.main.async { [weak self] in
      // Portrait: the app is locked to portrait, so the preview is too.
      if let connection = self?.previewLayer.connection, connection.isVideoRotationAngleSupported(90) {
        connection.videoRotationAngle = 90
      }
    }
  }
}
