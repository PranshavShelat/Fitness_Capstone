import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';
import 'package:flutter/foundation.dart';
import 'dart:io';

import 'utils.dart'; // Import our smoothing and math logic

late List<CameraDescription> _cameras;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  _cameras = await availableCameras();
  runApp(const FitnessApp());
}

class FitnessApp extends StatelessWidget {
  const FitnessApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Fitness Engine',
      theme: ThemeData(
        brightness: Brightness.dark,
        primarySwatch: Colors.blue,
        useMaterial3: true,
      ),
      home: const ExerciseSelectionScreen(),
    );
  }
}

class ExerciseSelectionScreen extends StatelessWidget {
  const ExerciseSelectionScreen({super.key});

  final List<String> exercises = const [
    "Squats", "Planks", "Tricep Dips", "Pushups", "Pullups",
    "Russian Twists", "Bicep Curls", "Hammer Curls", "Lateral Raises",
    "Shoulder Press", "Bench Press", "Chest Fly Machine", "Deadlift",
    "Decline Bench Press", "Hip Thrust", "Inclined Bench Press", 
    "Lat Pulldown", "Leg Extension", "Leg Raises", "Romanian Deadlifts",
    "T Bar Row", "Tricep Pushdowns"
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Select Exercise')),
      body: ListView.builder(
        itemCount: exercises.length,
        itemBuilder: (context, index) {
          return ListTile(
            title: Text(exercises[index]),
            trailing: const Icon(Icons.arrow_forward_ios),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => CameraScreen(exerciseName: exercises[index]),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class CameraScreen extends StatefulWidget {
  final String exerciseName;
  const CameraScreen({super.key, required this.exerciseName});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> {
  CameraController? _controller;
  late PoseDetector _poseDetector;
  bool _isProcessing = false;
  
  Map<PoseLandmarkType, SmoothedPoint>? _smoothedLandmarks;
  int _lastFrameTime = 0;
  
  CameraDescription? _camera;

  @override
  void initState() {
    super.initState();
    _poseDetector = PoseDetector(options: PoseDetectorOptions());
    _initCamera();
  }

  Future<void> _initCamera() async {
    for (var c in _cameras) {
      if (c.lensDirection == CameraLensDirection.front) {
        _camera = c;
        break;
      }
    }
    _camera ??= _cameras.first;

    _controller = CameraController(
      _camera!,
      ResolutionPreset.high,
      enableAudio: false,
      imageFormatGroup: Platform.isIOS
          ? ImageFormatGroup.bgra8888
          : ImageFormatGroup.yuv420,
    );

    try {
      await _controller!.initialize();
      if (!mounted) return;

      setState(() {});

      _controller!.startImageStream((CameraImage image) {
        if (!_isProcessing) {
          _processImage(image);
        }
      });
    } catch (e) {
      debugPrint("Camera Error: \$e");
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    _poseDetector.close();
    super.dispose();
  }

  Future<void> _processImage(CameraImage image) async {
    _isProcessing = true;

    try {
      final WriteBuffer allBytes = WriteBuffer();
      for (final Plane plane in image.planes) {
        allBytes.putUint8List(plane.bytes);
      }
      final bytes = allBytes.done().buffer.asUint8List();

      final Size imageSize = Size(image.width.toDouble(), image.height.toDouble());
      final InputImageRotation rotation = InputImageRotationValue.fromRawValue(_camera!.sensorOrientation) ?? InputImageRotation.rotation0deg;
      
      final inputImageData = InputImageMetadata(
        size: imageSize,
        rotation: rotation,
        format: InputImageFormatValue.fromRawValue(image.format.raw) ?? InputImageFormat.bgra8888,
        bytesPerRow: image.planes.first.bytesPerRow,
      );

      final inputImage = InputImage.fromBytes(
        bytes: bytes,
        metadata: inputImageData,
      );

      final poses = await _poseDetector.processImage(inputImage);
      if (mounted && poses.isNotEmpty) {
        final now = DateTime.now().millisecondsSinceEpoch;
        final double dt = _lastFrameTime > 0 ? (now - _lastFrameTime) / 1000.0 : 0.0;
        _lastFrameTime = now;

        setState(() {
          _smoothedLandmarks = smoothLandmarks(poses.first, _smoothedLandmarks, dt);
        });
      } else if (poses.isEmpty) {
        setState(() {
          _smoothedLandmarks = null;
        });
      }
    } catch (e) {
      debugPrint("ML Kit Error: \$e");
    } finally {
      _isProcessing = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_controller == null || !_controller!.value.isInitialized) {
      return Scaffold(
        appBar: AppBar(title: Text(widget.exerciseName)),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Tracking: \${widget.exerciseName}'),
        backgroundColor: Colors.black45,
        elevation: 0,
      ),
      backgroundColor: Colors.black,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final InputImageRotation mlRotation = InputImageRotationValue.fromRawValue(_camera!.sensorOrientation) ?? InputImageRotation.rotation0deg;

            // Fix the squished camera feed without breaking the coordinates
            final isPortraitUI = MediaQuery.of(context).orientation == Orientation.portrait;
            double ratio = _controller!.value.aspectRatio;
            if (isPortraitUI && ratio > 1.0) {
              ratio = 1.0 / ratio; // Make it a tall portrait ratio (e.g., 9:16 instead of 16:9)
            } else if (!isPortraitUI && ratio < 1.0) {
              ratio = 1.0 / ratio; // Keep it landscape if they turn the phone
            }

            return Stack(
              children: [
                Center(
                  child: AspectRatio(
                    aspectRatio: ratio,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        CameraPreview(_controller!),
                        if (_smoothedLandmarks != null)
                          CustomPaint(
                            painter: PosePainter(
                              smoothedLandmarks: _smoothedLandmarks!,
                              imageSize: Size(_controller!.value.previewSize!.width, _controller!.value.previewSize!.height),
                              rotation: mlRotation,
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
                Positioned(
                  bottom: 20,
                  left: 20,
                  right: 20,
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.black54,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      _smoothedLandmarks != null 
                        ? "Tracking Active! (\${_smoothedLandmarks!.length} landmarks)" 
                        : "Scanning for body...",
                      style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              ],
            );
          },
        ),
      ),
    );
  }
}

class PosePainter extends CustomPainter {
  final Map<PoseLandmarkType, SmoothedPoint> smoothedLandmarks;
  final Size imageSize;
  final InputImageRotation rotation;

  PosePainter({required this.smoothedLandmarks, required this.imageSize, required this.rotation});

  @override
  void paint(Canvas canvas, Size size) {
    // Exact Match to Python mp_drawing: Thin white lines, small red dots
    final linePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0
      ..color = Colors.white;

    final pointPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = Colors.red;

    final bool isPortraitImage = rotation == InputImageRotation.rotation90deg || rotation == InputImageRotation.rotation270deg;
    final double logicalWidth = isPortraitImage ? imageSize.height : imageSize.width;
    final double logicalHeight = isPortraitImage ? imageSize.width : imageSize.height;

    // Helper to translate a landmark type into a screen coordinate
    Offset? getOffset(PoseLandmarkType type) {
      final landmark = smoothedLandmarks[type];
      if (landmark == null) return null;

      final double scaleX = size.width / logicalWidth;
      final double scaleY = size.height / logicalHeight;

      // Restored non-mirrored coordinate system 
      final double x = landmark.x * scaleX;
      final double y = landmark.y * scaleY;
      return Offset(x, y);
    }

    // Helper to draw a connecting line
    void drawLine(PoseLandmarkType type1, PoseLandmarkType type2) {
      final offset1 = getOffset(type1);
      final offset2 = getOffset(type2);
      if (offset1 != null && offset2 != null) {
        canvas.drawLine(offset1, offset2, linePaint);
      }
    }

    // --- Exact MediaPipe POSE_CONNECTIONS ---
    // Face
    drawLine(PoseLandmarkType.nose, PoseLandmarkType.leftEyeInner);
    drawLine(PoseLandmarkType.leftEyeInner, PoseLandmarkType.leftEye);
    drawLine(PoseLandmarkType.leftEye, PoseLandmarkType.leftEyeOuter);
    drawLine(PoseLandmarkType.leftEyeOuter, PoseLandmarkType.leftEar);
    
    drawLine(PoseLandmarkType.nose, PoseLandmarkType.rightEyeInner);
    drawLine(PoseLandmarkType.rightEyeInner, PoseLandmarkType.rightEye);
    drawLine(PoseLandmarkType.rightEye, PoseLandmarkType.rightEyeOuter);
    drawLine(PoseLandmarkType.rightEyeOuter, PoseLandmarkType.rightEar);
    
    drawLine(PoseLandmarkType.leftMouth, PoseLandmarkType.rightMouth);

    // Torso
    drawLine(PoseLandmarkType.leftShoulder, PoseLandmarkType.rightShoulder);
    drawLine(PoseLandmarkType.leftShoulder, PoseLandmarkType.leftHip);
    drawLine(PoseLandmarkType.rightShoulder, PoseLandmarkType.rightHip);
    drawLine(PoseLandmarkType.leftHip, PoseLandmarkType.rightHip);

    // Left Arm & Hand
    drawLine(PoseLandmarkType.leftShoulder, PoseLandmarkType.leftElbow);
    drawLine(PoseLandmarkType.leftElbow, PoseLandmarkType.leftWrist);
    drawLine(PoseLandmarkType.leftWrist, PoseLandmarkType.leftPinky);
    drawLine(PoseLandmarkType.leftPinky, PoseLandmarkType.leftIndex);
    drawLine(PoseLandmarkType.leftIndex, PoseLandmarkType.leftWrist);
    drawLine(PoseLandmarkType.leftWrist, PoseLandmarkType.leftThumb);

    // Right Arm & Hand
    drawLine(PoseLandmarkType.rightShoulder, PoseLandmarkType.rightElbow);
    drawLine(PoseLandmarkType.rightElbow, PoseLandmarkType.rightWrist);
    drawLine(PoseLandmarkType.rightWrist, PoseLandmarkType.rightPinky);
    drawLine(PoseLandmarkType.rightPinky, PoseLandmarkType.rightIndex);
    drawLine(PoseLandmarkType.rightIndex, PoseLandmarkType.rightWrist);
    drawLine(PoseLandmarkType.rightWrist, PoseLandmarkType.rightThumb);

    // Left Leg & Foot
    drawLine(PoseLandmarkType.leftHip, PoseLandmarkType.leftKnee);
    drawLine(PoseLandmarkType.leftKnee, PoseLandmarkType.leftAnkle);
    drawLine(PoseLandmarkType.leftAnkle, PoseLandmarkType.leftHeel);
    drawLine(PoseLandmarkType.leftHeel, PoseLandmarkType.leftFootIndex);
    drawLine(PoseLandmarkType.leftFootIndex, PoseLandmarkType.leftAnkle);

    // Right Leg & Foot
    drawLine(PoseLandmarkType.rightHip, PoseLandmarkType.rightKnee);
    drawLine(PoseLandmarkType.rightKnee, PoseLandmarkType.rightAnkle);
    drawLine(PoseLandmarkType.rightAnkle, PoseLandmarkType.rightHeel);
    drawLine(PoseLandmarkType.rightHeel, PoseLandmarkType.rightFootIndex);
    drawLine(PoseLandmarkType.rightFootIndex, PoseLandmarkType.rightAnkle);

    // Draw all 33 raw landmarks on top
    for (final landmark in smoothedLandmarks.values) {
      final double scaleX = size.width / logicalWidth;
      final double scaleY = size.height / logicalHeight;
      final double x = landmark.x * scaleX;
      final double y = landmark.y * scaleY;
      canvas.drawCircle(Offset(x, y), 3.0, pointPaint);
    }
  }

  @override
  bool shouldRepaint(covariant PosePainter oldDelegate) {
    return true;
  }
}
