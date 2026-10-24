import ExpoModulesCore

// Bridge only: forwards calls to the shell and CaptureCore, holds no logic.
public class CaptureModule: Module {
  public func definition() -> ModuleDefinition {
    Name("Capture")

    // What the Capture screen shows (a CaptureReadiness raw value).
    Function("getReadiness") { () -> String in
      SensorPermissions.readiness().rawValue
    }

    // Prompts for every permission not decided yet, then returns the new readiness.
    AsyncFunction("requestPermissions") { () async -> String in
      await SensorPermissions.requestUndecided()
      return SensorPermissions.readiness().rawValue
    }

    View(CameraPreviewView.self) {}
  }
}
