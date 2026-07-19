import 'dart:math';
import 'package:flutter/material.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

class Utils {
  /// Calculates the 3D/2D angle between three points (a, b, c) where b is the vertex.
  static double calculateAngle(PoseLandmark a, PoseLandmark b, PoseLandmark c) {
    double radians = atan2(c.y - b.y, c.x - b.x) - atan2(a.y - b.y, a.x - b.x);
    double angle = (radians * 180.0 / pi).abs();

    if (angle > 180.0) {
      angle = 360.0 - angle;
    }
    return angle;
  }

  /// Debounces the stage to prevent flicker (Problem 2)
  static Map<String, dynamic> debounceStage(
      String newStage, String? confirmedStage, Map<String, dynamic>? pendingState,
      {int requiredFrames = 3}) {
    if (confirmedStage == null) {
      return {'stage': newStage, 'state': {'candidate': newStage, 'count': 0}};
    }

    pendingState ??= {'candidate': confirmedStage, 'count': 0};

    if (newStage == confirmedStage) {
      return {'stage': confirmedStage, 'state': {'candidate': confirmedStage, 'count': 0}};
    }

    if (pendingState['candidate'] == newStage) {
      pendingState['count'] = (pendingState['count'] as int) + 1;
    } else {
      pendingState = {'candidate': newStage, 'count': 1};
    }

    if ((pendingState['count'] as int) >= requiredFrames) {
      return {'stage': newStage, 'state': {'candidate': newStage, 'count': 0}};
    }

    return {'stage': confirmedStage, 'state': pendingState};
  }

  /// Stabilizes text feedback (Problem 3)
  static Map<String, dynamic> stabilizeFeedback(
      String newFb, Color newColor, Map<String, dynamic>? feedbackState,
      {int minHoldFrames = 4, Color dangerColor = Colors.red}) {
    
    if (feedbackState == null) {
      return {'fb': newFb, 'color': newColor, 'state': {'fb': newFb, 'color': newColor, 'candidate': newFb, 'count': 0}};
    }

    if (newColor == dangerColor) {
      return {'fb': newFb, 'color': newColor, 'state': {'fb': newFb, 'color': newColor, 'candidate': newFb, 'count': 0}};
    }

    if (newFb == feedbackState['fb']) {
      feedbackState['candidate'] = newFb;
      feedbackState['count'] = 0;
      return {'fb': feedbackState['fb'], 'color': feedbackState['color'], 'state': feedbackState};
    }

    if (feedbackState['candidate'] == newFb) {
      feedbackState['count'] = (feedbackState['count'] as int) + 1;
    } else {
      feedbackState['candidate'] = newFb;
      feedbackState['count'] = 1;
    }

    if ((feedbackState['count'] as int) >= minHoldFrames) {
      feedbackState['fb'] = newFb;
      feedbackState['color'] = newColor;
      feedbackState['count'] = 0;
    }

    return {'fb': feedbackState['fb'], 'color': feedbackState['color'], 'state': feedbackState};
  }
}
