import AVFoundation
import ExpoModulesCore

/// Shell: live preview of the back wide-angle camera. React Native mounts it only when
/// CaptureReadiness is `ready`. The session runs while the view is in a window. Setup or
/// runtime failures are sent to JS as `onCameraError` instead of leaving a black view.
class CameraPreviewView: ExpoView {
  let onCameraError = EventDispatcher()

  private let session = AVCaptureSession()
  private let sessionQueue = DispatchQueue(label: "capturekit.preview.session")
  private let previewLayer: AVCaptureVideoPreviewLayer
  private var isConfigured = false  // only touched on sessionQueue, true once setup succeeded

  required init(appContext: AppContext? = nil) {
    previewLayer = AVCaptureVideoPreviewLayer(session: session)
    super.init(appContext: appContext)
    clipsToBounds = true
    backgroundColor = .black
    previewLayer.videoGravity = .resizeAspectFill
    layer.addSublayer(previewLayer)
    NotificationCenter.default.addObserver(
      self, selector: #selector(sessionRuntimeError(_:)),
      name: AVCaptureSession.runtimeErrorNotification, object: session)
  }

  override func layoutSubviews() {
    super.layoutSubviews()
    // No implicit animation: the preview must follow the view's frame immediately.
    CATransaction.begin()
    CATransaction.setDisableActions(true)
    previewLayer.frame = bounds
    CATransaction.commit()
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
      do {
        try configure()
        isConfigured = true
      } catch {
        report(error.localizedDescription)
        return
      }
    }
    session.startRunning()
  }

  private func configure() throws {
    guard let camera = CameraPermissions.backCamera else {
      throw PreviewSetupError("No back camera found.")
    }
    let input = try AVCaptureDeviceInput(device: camera)
    session.beginConfiguration()
    defer { session.commitConfiguration() }
    guard session.canAddInput(input) else {
      throw PreviewSetupError("The back camera can't be added to the capture session.")
    }
    session.sessionPreset = .high
    session.addInput(input)
    DispatchQueue.main.async { [weak self] in
      // Portrait: the app is locked to portrait, so the preview is too.
      if let connection = self?.previewLayer.connection, connection.isVideoRotationAngleSupported(90) {
        connection.videoRotationAngle = 90
      }
    }
  }

  @objc private func sessionRuntimeError(_ notification: Notification) {
    let error = notification.userInfo?[AVCaptureSessionErrorKey] as? Error
    report(error?.localizedDescription ?? "The camera stopped unexpectedly.")
  }

  private func report(_ message: String) {
    DispatchQueue.main.async { [weak self] in
      self?.onCameraError(["message": message])
    }
  }
}

private struct PreviewSetupError: LocalizedError {
  let errorDescription: String?
  init(_ message: String) { errorDescription = message }
}
