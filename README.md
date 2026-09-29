# Hand Gesture Control System

A real-time computer control and drawing system using hand gestures.

## Features

- Hand gesture based mouse control
- Left click
- Right click
- Double click
- Screen cursor movement
- Drawing mode
- Dynamic background-adaptive drawing color
- Local area eraser
- Lock/unlock system
- Webcam based real-time hand tracking
- Video recording

## Technologies Used

- Python
- OpenCV
- MediaPipe
- NumPy
- PyAutoGUI / Mouse Control
- Webcam

## How It Works

The system uses MediaPipe to detect hand landmarks through the webcam. Different hand gestures are interpreted as mouse actions or drawing commands.

### Mouse Mode

| Gesture | Action |
|---|---|
| Thumb + Index | Left Click |
| Index + Middle | Right Click |
| Thumb touching Index/Middle area | Double Click |
| Fist | Lock |

### Drawing Mode

| Gesture | Action |
|---|---|
| Index finger | Draw |
| Index + Middle | Pen Up |
| Open Palm | Erase |
| Fist | Does not lock |

## Installation

```bash
pip install opencv-python mediapipe numpy mouse