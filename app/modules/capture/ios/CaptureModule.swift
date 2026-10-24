import ExpoModulesCore

public class CaptureModule: Module {
  public func definition() -> ModuleDefinition {
    Name("Capture")

    Function("hello") {
      return "Hello world! 👋"
    }

    View(CaptureView.self) {
    }
  }
}
