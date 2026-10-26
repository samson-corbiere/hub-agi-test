Pod::Spec.new do |s|
  s.name           = 'Capture'
  s.version        = '0.1.0'
  s.summary        = 'CaptureKit native capture module'
  s.description    = 'Camera preview, capture, storage and upload for CaptureKit, exposed to React Native.'
  s.author         = ''
  s.license        = 'MIT'
  s.homepage       = 'https://github.com/samson-corbiere/hub-agi-test'
  s.platforms      = {
    :ios => '17.0'
  }
  s.source         = { git: '' }
  s.static_framework = true

  s.dependency 'ExpoModulesCore'

  # Swift/Objective-C compatibility
  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
  }

  # The Expo shell (this folder) plus the pure CaptureCore sources, compiled into one
  # module. CaptureCore's Package.swift and Tests are for `swift test` only.
  s.source_files = [
    '*.swift',
    'CaptureCore/Sources/CaptureCore/**/*.swift'
  ]
end
