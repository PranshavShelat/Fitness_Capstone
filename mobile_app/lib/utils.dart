import 'dart:math' as math;
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

class SmoothedPoint {
  final double x;
  final double y;
  final double z;
  final double likelihood;

  SmoothedPoint({
    required this.x,
    required this.y,
    required this.z,
    required this.likelihood,
  });
}

Map<PoseLandmarkType, SmoothedPoint> smoothLandmarks(
  Pose currentPose,
  Map<PoseLandmarkType, SmoothedPoint>? prevSmoothed,
  double dt, {
  double tau = 0.05, // Drastically reduced for faster response (as in step 692)
  double minVisibility = 0.5,
  double lowConfAlphaScale = 0.25,
}) {
  final Map<PoseLandmarkType, SmoothedPoint> result = {};

  for (final type in currentPose.landmarks.keys) {
    final landmark = currentPose.landmarks[type]!;
    final prev = prevSmoothed?[type];

    if (prev == null || dt <= 0.0) {
      result[type] = SmoothedPoint(
        x: landmark.x,
        y: landmark.y,
        z: landmark.z,
        likelihood: landmark.likelihood,
      );
      continue;
    }

    double alpha = dt / (tau + dt);
    if (landmark.likelihood < minVisibility) {
      alpha *= lowConfAlphaScale;
    }

    final double smoothedX = (alpha * landmark.x) + ((1 - alpha) * prev.x);
    final double smoothedY = (alpha * landmark.y) + ((1 - alpha) * prev.y);
    final double smoothedZ = (alpha * landmark.z) + ((1 - alpha) * prev.z);

    result[type] = SmoothedPoint(
      x: smoothedX,
      y: smoothedY,
      z: smoothedZ,
      likelihood: landmark.likelihood,
    );
  }

  return result;
}

double calculateAngle(SmoothedPoint a, SmoothedPoint b, SmoothedPoint c) {
  final double radians = math.atan2(c.y - b.y, c.x - b.x) - math.atan2(a.y - b.y, a.x - b.x);
  double angle = (radians * 180.0 / math.pi).abs();
  if (angle > 180.0) {
    angle = 360.0 - angle;
  }
  return angle;
}
