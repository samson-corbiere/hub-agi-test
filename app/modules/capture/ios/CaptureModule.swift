import ExpoModulesCore

// Bridge only: forwards calls to the shell and CaptureCore, holds no logic.
public class CaptureModule: Module {
  public func definition() -> ModuleDefinition {
    Name("Capture")

    // What the Capture screen shows (a CaptureReadiness raw value).
    Function("getReadiness") { () -> String in
      CameraPermissions.readiness().rawValue
    }

    // Prompts for the camera if not decided yet, then returns the new readiness.
    AsyncFunction("requestPermissions") { () async -> String in
      await CameraPermissions.requestIfUndecided()
      return CameraPermissions.readiness().rawValue
    }

    View(CameraPreviewView.self) {
      // { message: String }: the camera could not be set up or stopped with an error.
      Events("onCameraError")
    }
  }
}
