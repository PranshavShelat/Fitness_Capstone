class Config {
  static const Map<String, double> squatSettings = {
    'STAND': 160.0, 'GOOD_MAX': 54.8, 'GOOD_MIN': 19.8, 'BACK_TOO_UPRIGHT': 5.0, 'BACK_PERFECT_MAX': 45.0, 'BACK_WARNING_MAX': 60.0, 'TARGET_DEPTH': 29.8
  };
  static const Map<String, double> plankSettings = {
    'HIP_MIN': 123.9, 'KNEE_MIN': 156.6
  };
  static const Map<String, double> dipSettings = {
    'UP_STATE': 150.0, 'TARGET_DEPTH': 67.0, 'BUFFER': 15.0
  };
  static const Map<String, double> pushupSettings = {
    'UP_STATE': 150.0, 'TARGET_DEPTH': 29.4, 'BUFFER': 25.0, 'HIP_MIN': 150.0
  };
  static const Map<String, double> pullupSettings = {
    'HANG_STATE': 150.0, 'TARGET_TOP': 25.4, 'BUFFER': 20.0
  };
  static const Map<String, double> twistSettings = {
    'TARGET_POSTURE': 80.0, 'BUFFER': 15.0
  };
  static const Map<String, double> bicepSettings = {
    'EXTENDED': 150.0, 'TARGET_FLEX': 26.0, 'BUFFER': 15.0
  };
  static const Map<String, double> hammerSettings = {
    'EXTENDED': 150.0, 'TARGET_FLEX': 40.4, 'BUFFER': 15.0
  };
  static const Map<String, double> lateralSettings = {
    'DOWN': 30.0, 'TARGET_UP': 85.0, 'BUFFER': 15.0, 'ELBOW_MIN': 140.0
  };
  static const Map<String, double> pressSettings = {
    'START': 90.0, 'TARGET_EXTENSION': 160.2, 'BUFFER': 15.0
  };
  static const Map<String, double> benchSettings = {
    'LOCKOUT': 165.0, 'TARGET_DEPTH': 23.6, 'BUFFER': 15.0, 'MAX_ASYMMETRY': 40.0, 'MAX_FLARE': 85.0
  };
}
