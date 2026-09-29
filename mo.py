import mediapipe as mp
import cv2
import mouse
import numpy as np
import math
import time


# ============================================================
# CAMERA
# ============================================================

cam = cv2.VideoCapture(0)

cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)


# ============================================================
# SCREEN RESOLUTION
# ============================================================

try:
    import ctypes

    user32 = ctypes.windll.user32

    SCREEN_W = user32.GetSystemMetrics(0)
    SCREEN_H = user32.GetSystemMetrics(1)

except Exception:

    SCREEN_W = 1920
    SCREEN_H = 1080

print(f"Detected screen resolution: {SCREEN_W}x{SCREEN_H}")


# ============================================================
# MEDIAPIPE
# ============================================================

mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands


# ============================================================
# VIDEO OUTPUT
# ============================================================

out = cv2.VideoWriter(
    "out.avi",
    cv2.VideoWriter_fourcc(*"XVID"),
    30,
    (640, 480)
)


# ============================================================
# DRAW MODE
# ============================================================

draw_mode = False

canvas = None
prev_point = None

# Default color
# Fluorescent green
draw_color = (0, 255, 0)

draw_thickness = 6


# ============================================================
# ERASER
# ============================================================

ERASER_RADIUS = 45


# ============================================================
# CURSOR SMOOTHING
# ============================================================

smoothed_x = None
smoothed_y = None

smoothing = 0.5


# ============================================================
# LOCK / UNLOCK
# ============================================================

system_locked = True

palm_open_start_time = None

UNLOCK_HOLD_SECONDS = 2.0

# NO AUTO LOCK


# ============================================================
# MOUSE GESTURE SETTINGS
# ============================================================

check_every = 2
check_cnt = 0

prev_gesture = None

candidate_gesture = None
candidate_count = 0

GESTURE_CONFIRM_COUNT = 2

last_action_time = 0

CLICK_COOLDOWN = 0.35


# ============================================================
# DYNAMIC INK COLOR
# ============================================================

def get_dynamic_ink_color(frame, point, sample_radius=15):
    """
    Select an ink color which contrasts with the
    background underneath the drawing point.
    """

    if point is None:
        return (0, 255, 0)

    x, y = point

    h, w, _ = frame.shape

    x1 = max(0, x - sample_radius)
    x2 = min(w, x + sample_radius)

    y1 = max(0, y - sample_radius)
    y2 = min(h, y + sample_radius)

    region = frame[y1:y2, x1:x2]

    if region.size == 0:
        return (0, 255, 0)

    # Convert background to grayscale
    gray = cv2.cvtColor(
        region,
        cv2.COLOR_BGR2GRAY
    )

    brightness = np.mean(gray)

    # -----------------------------------------
    # DARK BACKGROUND
    # -----------------------------------------
    # Fluorescent green
    if brightness < 80:

        return (0, 255, 0)

    # -----------------------------------------
    # MEDIUM BACKGROUND
    # -----------------------------------------
    # Bright cyan
    elif brightness < 150:

        return (255, 255, 0)

    # -----------------------------------------
    # BRIGHT BACKGROUND
    # -----------------------------------------
    # Dark blue
    else:

        return (180, 0, 0)


# ============================================================
# OTHER FUNCTIONS
# ============================================================

def distance(p1, p2):

    if p1 is None or p2 is None:
        return float("inf")

    return math.dist(p1, p2)


def get_point(landmark, w, h):

    return mp_drawing._normalized_to_pixel_coordinates(
        landmark.x,
        landmark.y,
        w,
        h
    )


def fingers_up(landmarks):

    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]

    fingers = []

    for tip, pip in zip(tips, pips):

        fingers.append(
            landmarks[tip].y <
            landmarks[pip].y
        )

    index_up = fingers[0]
    middle_up = fingers[1]
    ring_up = fingers[2]
    pinky_up = fingers[3]

    # Original thumb detection
    thumb_up = landmarks[4].x > landmarks[3].x

    return (
        thumb_up,
        index_up,
        middle_up,
        ring_up,
        pinky_up
    )


def get_palm_center(landmarks, w, h):

    ids = [
        mp_hands.HandLandmark.WRIST,
        mp_hands.HandLandmark.INDEX_FINGER_MCP,
        mp_hands.HandLandmark.MIDDLE_FINGER_MCP,
        mp_hands.HandLandmark.RING_FINGER_MCP,
        mp_hands.HandLandmark.PINKY_MCP
    ]

    points = []

    for landmark_id in ids:

        point = get_point(
            landmarks[landmark_id],
            w,
            h
        )

        if point is not None:

            points.append(point)

    if not points:

        return None

    x = int(
        sum(p[0] for p in points) /
        len(points)
    )

    y = int(
        sum(p[1] for p in points) /
        len(points)
    )

    return (x, y)


def erase_area(canvas, center, radius):

    if center is None:
        return

    cv2.circle(
        canvas,
        center,
        radius,
        (0, 0, 0),
        -1
    )


# ============================================================
# MEDIAPIPE
# ============================================================

with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.4,
        min_tracking_confidence=0.4
) as hands:

    while cam.isOpened():

        ret, frame = cam.read()

        if not ret:
            continue


        # ====================================================
        # MIRROR CAMERA
        # ====================================================

        frame = cv2.flip(frame, 1)

        h, w, _ = frame.shape


        # ====================================================
        # CREATE CANVAS
        # ====================================================

        if canvas is None:

            canvas = np.zeros(
                (h, w, 3),
                dtype=np.uint8
            )


        # ====================================================
        # MEDIAPIPE
        # ====================================================

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        res = hands.process(rgb)


        # ====================================================
        # STATUS BAR
        # ====================================================

        cv2.rectangle(
            frame,
            (0, 0),
            (w, 35),
            (30, 30, 30),
            -1
        )


        if system_locked:

            mode_text = (
                "LOCKED - Hold OPEN PALM for 2 seconds"
            )

            bar_color = (0, 0, 255)

        else:

            if draw_mode:

                mode_text = (
                    "DRAW MODE | D = Mouse | C = Clear"
                )

            else:

                mode_text = (
                    "MOUSE MODE | D = Draw | FIST = Lock"
                )

            bar_color = (0, 255, 0)


        cv2.putText(
            frame,
            mode_text,
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            bar_color,
            1
        )


        # ====================================================
        # LEGEND
        # ====================================================

        if not system_locked:

            if draw_mode:

                legend = [
                    "INDEX = DRAW",
                    "INDEX + MIDDLE = PEN UP",
                    "OPEN PALM = LOCAL ERASER"
                ]

            else:

                legend = [
                    "THUMB + INDEX = LEFT CLICK",
                    "INDEX + MIDDLE = RIGHT CLICK",
                    "THUMB + INDEX/MIDDLE = DOUBLE CLICK",
                    "FIST = LOCK"
                ]

            for i, text in enumerate(legend):

                cv2.putText(
                    frame,
                    text,
                    (10, 55 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.44,
                    (200, 200, 0),
                    1
                )


        # ====================================================
        # HAND DETECTED
        # ====================================================

        if res.multi_hand_landmarks:

            for hand_landmarks in res.multi_hand_landmarks:

                landmarks = hand_landmarks.landmark


                # =================================================
                # FINGER STATES
                # =================================================

                (
                    thumb_up,
                    index_up,
                    middle_up,
                    ring_up,
                    pinky_up
                ) = fingers_up(landmarks)


                # =================================================
                # OPEN PALM
                # =================================================

                all_open = (
                    thumb_up
                    and index_up
                    and middle_up
                    and ring_up
                    and pinky_up
                )


                # =================================================
                # FIST
                # =================================================

                is_fist = (
                    not index_up
                    and not middle_up
                    and not ring_up
                    and not pinky_up
                )


                # =================================================
                # LOCKED STATE
                # =================================================

                if system_locked:

                    if all_open:

                        if palm_open_start_time is None:

                            palm_open_start_time = time.time()

                        elapsed = (
                            time.time()
                            - palm_open_start_time
                        )

                        progress = min(
                            elapsed /
                            UNLOCK_HOLD_SECONDS,
                            1.0
                        )

                        bar_width = int(
                            300 * progress
                        )


                        cv2.rectangle(
                            frame,
                            (10, h - 50),
                            (10 + bar_width, h - 35),
                            (0, 255, 255),
                            -1
                        )


                        cv2.rectangle(
                            frame,
                            (10, h - 50),
                            (310, h - 35),
                            (255, 255, 255),
                            2
                        )


                        cv2.putText(
                            frame,
                            "Unlocking... "
                            f"{int(progress * 100)}%",
                            (10, h - 60),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 255),
                            2
                        )


                        if elapsed >= UNLOCK_HOLD_SECONDS:

                            system_locked = False

                            palm_open_start_time = None

                            prev_gesture = None
                            candidate_gesture = None
                            candidate_count = 0

                            print("UNLOCKED")

                    else:

                        palm_open_start_time = None


                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS
                    )

                    continue


                # =================================================
                # FIST LOCK
                #
                # ONLY MOUSE MODE
                # =================================================

                if not draw_mode and is_fist:

                    system_locked = True

                    palm_open_start_time = None

                    prev_gesture = None
                    candidate_gesture = None
                    candidate_count = 0

                    print("LOCKED")


                    cv2.putText(
                        frame,
                        "LOCKED",
                        (10, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 0, 255),
                        2
                    )


                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS
                    )

                    continue


                # =================================================
                # LANDMARKS
                # =================================================

                index_tip = get_point(
                    landmarks[
                        mp_hands.HandLandmark.INDEX_FINGER_TIP
                    ],
                    w,
                    h
                )

                thumb_tip = get_point(
                    landmarks[
                        mp_hands.HandLandmark.THUMB_TIP
                    ],
                    w,
                    h
                )

                middle_tip = get_point(
                    landmarks[
                        mp_hands.HandLandmark.MIDDLE_FINGER_TIP
                    ],
                    w,
                    h
                )

                palm_center = get_palm_center(
                    landmarks,
                    w,
                    h
                )


                # =================================================
                # DRAW MODE
                # =================================================

                if draw_mode:

                    # ---------------------------------------------
                    # OPEN PALM = LOCAL ERASER
                    # ---------------------------------------------

                    if all_open:

                        prev_point = None

                        erase_area(
                            canvas,
                            palm_center,
                            ERASER_RADIUS
                        )


                        if palm_center is not None:

                            cv2.circle(
                                frame,
                                palm_center,
                                ERASER_RADIUS,
                                (0, 0, 255),
                                2
                            )


                        cv2.putText(
                            frame,
                            "ERASING",
                            (10, h - 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 0, 255),
                            2
                        )


                    # ---------------------------------------------
                    # INDEX ONLY = DRAW
                    # ---------------------------------------------

                    elif (
                        index_up
                        and not middle_up
                        and not ring_up
                        and not pinky_up
                    ):

                        if index_tip is not None:

                            # Get a color based on the actual
                            # camera background at this location.
                            draw_color = get_dynamic_ink_color(
                                frame,
                                index_tip
                            )


                            if prev_point is not None:

                                cv2.line(
                                    canvas,
                                    prev_point,
                                    index_tip,
                                    draw_color,
                                    draw_thickness
                                )


                            prev_point = index_tip


                        cv2.putText(
                            frame,
                            "DRAWING",
                            (10, h - 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            draw_color,
                            2
                        )


                    # ---------------------------------------------
                    # INDEX + MIDDLE = PEN UP
                    # ---------------------------------------------

                    elif (
                        index_up
                        and middle_up
                        and not ring_up
                        and not pinky_up
                    ):

                        prev_point = None

                        cv2.putText(
                            frame,
                            "PEN UP",
                            (10, h - 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 255),
                            2
                        )


                    else:

                        prev_point = None


                # =================================================
                # MOUSE MODE
                # =================================================

                else:

                    # =================================================
                    # DISTANCES
                    # =================================================

                    thumb_index_dist = distance(
                        thumb_tip,
                        index_tip
                    )

                    thumb_middle_dist = distance(
                        thumb_tip,
                        middle_tip
                    )

                    index_middle_dist = distance(
                        index_tip,
                        middle_tip
                    )


                    # =================================================
                    # DEBUG DISTANCES
                    # =================================================

                    cv2.putText(
                        frame,
                        f"T-I: {int(thumb_index_dist)}",
                        (w - 150, 55),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 255, 255),
                        1
                    )

                    cv2.putText(
                        frame,
                        f"T-M: {int(thumb_middle_dist)}",
                        (w - 150, 75),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 255, 255),
                        1
                    )

                    cv2.putText(
                        frame,
                        f"I-M: {int(index_middle_dist)}",
                        (w - 150, 95),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 255, 255),
                        1
                    )


                    # =================================================
                    # GESTURE CHECK
                    # =================================================

                    if check_cnt >= check_every:

                        detected = None


                        # =================================================
                        # DOUBLE CLICK
                        #
                        # Thumb touches index/middle area
                        #
                        # Checked FIRST because it overlaps
                        # with other gestures.
                        # =================================================

                        if (
                            index_up
                            and middle_up
                            and not ring_up
                            and not pinky_up
                            and
                            (
                                thumb_index_dist < 70
                                or
                                thumb_middle_dist < 70
                            )
                        ):

                            detected = "dclick"


                        # =================================================
                        # RIGHT CLICK
                        #
                        # INDEX + MIDDLE
                        #
                        # Thumb NOT required.
                        # =================================================

                        elif (
                            index_up
                            and middle_up
                            and not ring_up
                            and not pinky_up
                            and index_middle_dist < 55
                        ):

                            detected = "rclick"


                        # =================================================
                        # LEFT CLICK
                        #
                        # THUMB + INDEX
                        # =================================================

                        elif (
                            index_up
                            and not middle_up
                            and not ring_up
                            and not pinky_up
                            and thumb_index_dist < 70
                        ):

                            detected = "sclick"


                        # =================================================
                        # GESTURE STABILITY
                        # =================================================

                        if detected == candidate_gesture:

                            candidate_count += 1

                        else:

                            candidate_gesture = detected

                            candidate_count = 1


                        # =================================================
                        # CONFIRM GESTURE
                        # =================================================

                        if candidate_count >= GESTURE_CONFIRM_COUNT:

                            current_time = time.time()


                            # Gesture changed
                            if detected != prev_gesture:


                                # -----------------------------------------
                                # LEFT CLICK
                                # -----------------------------------------

                                if (
                                    detected == "sclick"
                                    and
                                    current_time -
                                    last_action_time
                                    > CLICK_COOLDOWN
                                ):

                                    mouse.click()

                                    print("LEFT CLICK")

                                    last_action_time = current_time


                                # -----------------------------------------
                                # RIGHT CLICK
                                # -----------------------------------------

                                elif (
                                    detected == "rclick"
                                    and
                                    current_time -
                                    last_action_time
                                    > CLICK_COOLDOWN
                                ):

                                    mouse.right_click()

                                    print("RIGHT CLICK")

                                    last_action_time = current_time


                                # -----------------------------------------
                                # DOUBLE CLICK
                                # -----------------------------------------

                                elif (
                                    detected == "dclick"
                                    and
                                    current_time -
                                    last_action_time
                                    > CLICK_COOLDOWN
                                ):

                                    mouse.double_click()

                                    print("DOUBLE CLICK")

                                    last_action_time = current_time


                                prev_gesture = detected


                            # Reset after no gesture
                            if detected is None:

                                prev_gesture = None


                            check_cnt = 0


                    # =================================================
                    # CURSOR MOVEMENT
                    # =================================================

                    if index_tip is not None:

                        raw_x = (
                            SCREEN_W *
                            index_tip[0] /
                            w
                        )

                        raw_y = (
                            SCREEN_H *
                            index_tip[1] /
                            h
                        )


                        if smoothed_x is None:

                            smoothed_x = raw_x
                            smoothed_y = raw_y

                        else:

                            smoothed_x += (
                                raw_x -
                                smoothed_x
                            ) * (1 - smoothing)

                            smoothed_y += (
                                raw_y -
                                smoothed_y
                            ) * (1 - smoothing)


                        mouse.move(
                            int(smoothed_x),
                            int(smoothed_y)
                        )


                    check_cnt += 1


                    # =================================================
                    # ACTION DISPLAY
                    # =================================================

                    action_text = (
                        prev_gesture
                        if prev_gesture is not None
                        else "none"
                    )


                    cv2.putText(
                        frame,
                        f"Action: {action_text}",
                        (10, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2
                    )


                # =================================================
                # DRAW LANDMARKS
                # =================================================

                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )


        # ========================================================
        # NO HAND DETECTED
        # ========================================================

        else:

            prev_point = None

            # No auto-lock
            # The system stays unlocked.

            prev_gesture = None

            candidate_gesture = None
            candidate_count = 0

            palm_open_start_time = None


        # ========================================================
        # SHOW CANVAS
        # ========================================================

        if draw_mode:

            frame = cv2.addWeighted(
                frame,
                1.0,
                canvas,
                1.0,
                0
            )


        # ========================================================
        # DISPLAY
        # ========================================================

        cv2.imshow(
            "Window",
            frame
        )

        out.write(frame)


        # ========================================================
        # KEYBOARD
        # ========================================================

        key = cv2.waitKey(3) & 0xFF


        # Quit
        if key == ord("q"):

            break


        # Toggle draw/mouse
        elif key == ord("d"):

            draw_mode = not draw_mode

            prev_point = None

            prev_gesture = None
            candidate_gesture = None
            candidate_count = 0

            print(
                f"Draw mode: {draw_mode}"
            )


        # Clear
        elif key == ord("c"):

            canvas = np.zeros(
                (h, w, 3),
                dtype=np.uint8
            )

            prev_point = None

            print("Canvas cleared")


# ============================================================
# CLEANUP
# ============================================================

cam.release()

out.release()

cv2.destroyAllWindows()