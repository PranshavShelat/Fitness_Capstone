import mediapipe as mp
from PIL import Image, ImageDraw, ImageFont

PoseLandmark = mp.solutions.pose.PoseLandmark

# A reduced set of connections - just the limbs/torso relevant to exercise form,
# not MediaPipe's full 33-point face/hand mesh.
BODY_CONNECTIONS = [
    (PoseLandmark.LEFT_SHOULDER, PoseLandmark.RIGHT_SHOULDER),
    (PoseLandmark.LEFT_SHOULDER, PoseLandmark.LEFT_ELBOW),
    (PoseLandmark.LEFT_ELBOW, PoseLandmark.LEFT_WRIST),
    (PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_ELBOW),
    (PoseLandmark.RIGHT_ELBOW, PoseLandmark.RIGHT_WRIST),
    (PoseLandmark.LEFT_HIP, PoseLandmark.RIGHT_HIP),
    (PoseLandmark.LEFT_SHOULDER, PoseLandmark.LEFT_HIP),
    (PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_HIP),
    (PoseLandmark.LEFT_HIP, PoseLandmark.LEFT_KNEE),
    (PoseLandmark.LEFT_KNEE, PoseLandmark.LEFT_ANKLE),
    (PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_KNEE),
    (PoseLandmark.RIGHT_KNEE, PoseLandmark.RIGHT_ANKLE),
]

JOINTS = sorted({joint for pair in BODY_CONNECTIONS for joint in pair}, key=lambda j: j.value)

CANVAS_SIZE = (300, 400)
MARGIN = 40
GRAY = (170, 170, 170)
RED = (220, 40, 40)


def render_fault_diagram(landmarks, highlight, label):
    """landmarks: 33-entry list of {x, y, ...} dicts (MediaPipe order, normalized 0-1).
    highlight: list of PoseLandmark members to circle/label in red.
    Returns a PIL.Image.Image - fpdf2's image() accepts this directly.
    """
    highlight_set = set(highlight)
    indices = [joint.value for joint in JOINTS]

    xs = [landmarks[i]["x"] for i in indices]
    ys = [landmarks[i]["y"] for i in indices]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    span_x = max(maxx - minx, 1e-6)
    span_y = max(maxy - miny, 1e-6)

    width, height = CANVAS_SIZE
    avail_w = width - 2 * MARGIN
    avail_h = height - 2 * MARGIN
    scale = min(avail_w / span_x, avail_h / span_y)
    offset_x = MARGIN + (avail_w - span_x * scale) / 2
    offset_y = MARGIN + (avail_h - span_y * scale) / 2

    def to_px(joint):
        lm = landmarks[joint.value]
        px = offset_x + (lm["x"] - minx) * scale
        py = offset_y + (lm["y"] - miny) * scale
        return (px, py)

    img = Image.new("RGB", CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(img)

    for a, b in BODY_CONNECTIONS:
        is_highlighted = a in highlight_set and b in highlight_set
        draw.line(
            [to_px(a), to_px(b)],
            fill=RED if is_highlighted else GRAY,
            width=5 if is_highlighted else 3,
        )

    for joint in JOINTS:
        x, y = to_px(joint)
        is_highlighted = joint in highlight_set
        r = 7 if is_highlighted else 4
        draw.ellipse([x - r, y - r, x + r, y + r], fill=RED if is_highlighted else GRAY)

    if highlight:
        label_points = [to_px(joint) for joint in highlight]
        label_x = sum(p[0] for p in label_points) / len(label_points)
        label_y = min(p[1] for p in label_points) - 20
        font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text((label_x - text_w / 2, max(label_y, 4)), label, fill=RED, font=font)

    return img
