import cv2
import mediapipe as mp
import random
import time
import json
import os
import math

# =========================================================
# CONFIGURATION
# =========================================================

CAMERA_INDEX = 0
WINDOW_NAME = "MAGIC MOTION QUIZ"

START_TIMER_SECONDS = 10 * 60

BALL_RADIUS = 35

BULLET_SPEED = 750.0
BULLET_COLOR = (80, 255, 255)

SHOOT_COOLDOWN = 0.35
COUNTDOWN_DURATION = 3

BALL_IMAGE_PATH = "ball.jpg"
BOMB_IMAGE_PATH = "bomb.png"

BOMB_CHANCE = 0.25
BOMB_TIME_PENALTY = 5 * 60

BASE_FALL_SPEED = 3.0
SPEED_BOOST_PER_CORRECT = 0.6
MAX_FALL_SPEED = 20.0

# =========================================================
# LOAD QUESTIONS
# =========================================================

QUESTIONS_DATA = []

try:
    with open("questions.json", "r") as f:
        QUESTIONS_DATA = json.load(f)["questions"]
except Exception as e:
    print("JSON ERROR:", e)

# =========================================================
# PARTICLES
# =========================================================

class Particle:

    def __init__(self, x, y, color, life=0.5, size=4):

        ang = random.uniform(0, math.tau)
        spd = random.uniform(120, 360)

        self.x = x
        self.y = y

        self.vx = math.cos(ang) * spd
        self.vy = math.sin(ang) * spd

        self.life = life
        self.max_life = life

        self.color = color
        self.size = size

    def update(self, dt):

        self.x += self.vx * dt
        self.y += self.vy * dt

        self.vy += 600 * dt

        self.life -= dt

    def draw(self, frame):

        if self.life <= 0:
            return

        alpha = self.life / self.max_life

        r = max(1, int(self.size * alpha))

        c = (
            int(self.color[0] * alpha),
            int(self.color[1] * alpha),
            int(self.color[2] * alpha)
        )

        cv2.circle(
            frame,
            (int(self.x), int(self.y)),
            r,
            c,
            -1
        )

# =========================================================
# BULLET
# =========================================================

class Bullet:

    def __init__(self, x, y, dx, dy):

        self.x = float(x)
        self.y = float(y)

        self.dx = float(dx)
        self.dy = float(dy)

        self.spawn_time = time.time()

        self.trail = []

    def update(self, dt):

        self.x += self.dx * dt
        self.y += self.dy * dt

        self.trail.append((self.x, self.y))

        if len(self.trail) > 12:
            self.trail.pop(0)

    def draw(self, frame):

        n = len(self.trail)

        for i, (tx, ty) in enumerate(self.trail):

            a = (i + 1) / max(1, n)

            r = max(1, int(2 + 6 * a))

            col = (
                int(80 * a),
                int(255 * a),
                int(255 * a)
            )

            cv2.circle(
                frame,
                (int(tx), int(ty)),
                r,
                col,
                -1
            )

        cv2.circle(
            frame,
            (int(self.x), int(self.y)),
            14,
            (40, 180, 200),
            -1,
            cv2.LINE_AA
        )

        cv2.circle(
            frame,
            (int(self.x), int(self.y)),
            8,
            BULLET_COLOR,
            -1,
            cv2.LINE_AA
        )

        cv2.circle(
            frame,
            (int(self.x), int(self.y)),
            4,
            (255, 255, 255),
            -1,
            cv2.LINE_AA
        )

# =========================================================
# FALLING OBJECT
# =========================================================

class FallingObject:

    def __init__(self, w, h):

        self.w = w
        self.h = h

        self.ball_img = cv2.imread(BALL_IMAGE_PATH, cv2.IMREAD_UNCHANGED)
        self.bomb_img = cv2.imread(BOMB_IMAGE_PATH, cv2.IMREAD_UNCHANGED)

        self.fall_speed = BASE_FALL_SPEED

        self.angle = 0

        self.reset()

    def reset(self):

        self.x = random.randint(80, self.w - 80)
        self.y = -80

        self.angle = 0

        if random.random() < BOMB_CHANCE:

            self.type = "bomb"
            self.img = self.bomb_img

        else:

            self.type = "ball"
            self.img = self.ball_img

    def update(self, dt):

        self.y += self.fall_speed * 60 * dt

        self.angle += 180 * dt

        if self.y > self.h + 80:
            self.reset()

    def increase_speed(self):

        self.fall_speed = min(
            MAX_FALL_SPEED,
            self.fall_speed + SPEED_BOOST_PER_CORRECT
        )

    def draw(self, frame):

        if self.img is not None:

            img = cv2.resize(self.img, (80, 80))

            M = cv2.getRotationMatrix2D(
                (40, 40),
                self.angle,
                1.0
            )

            img = cv2.warpAffine(
                img,
                M,
                (80, 80),
                borderValue=(0, 0, 0, 0)
            )

            x1 = int(self.x - 40)
            y1 = int(self.y - 40)

            x2 = x1 + 80
            y2 = y1 + 80

            if x1 < 0 or y1 < 0 or x2 > self.w or y2 > self.h:
                return

            if img.ndim == 3 and img.shape[2] == 4:

                alpha = img[:, :, 3] / 255.0

                for c in range(3):

                    frame[y1:y2, x1:x2, c] = (
                        alpha * img[:, :, c]
                        + (1 - alpha) * frame[y1:y2, x1:x2, c]
                    )

            else:

                frame[y1:y2, x1:x2] = img[:, :, :3]

        else:

            color = (0, 0, 255) if self.type == "bomb" else (0, 255, 0)

            cv2.circle(
                frame,
                (int(self.x), int(self.y)),
                BALL_RADIUS,
                color,
                -1
            )

# =========================================================
# HELPERS
# =========================================================

def draw_fancy_text(
    img,
    text,
    pos,
    size=1.0,
    color=(255, 255, 255),
    thickness=2
):

    x, y = pos

    cv2.putText(
        img,
        str(text),
        (x + 2, y + 2),
        cv2.FONT_HERSHEY_DUPLEX,
        size,
        (0, 0, 0),
        thickness + 2,
        cv2.LINE_AA
    )

    cv2.putText(
        img,
        str(text),
        (x, y),
        cv2.FONT_HERSHEY_DUPLEX,
        size,
        color,
        thickness,
        cv2.LINE_AA
    )

def draw_panel(
    frame,
    x1,
    y1,
    x2,
    y2,
    color=(20, 20, 30),
    alpha=0.6,
    border=(80, 200, 255)
):

    overlay = frame.copy()

    cv2.rectangle(
        overlay,
        (x1, y1),
        (x2, y2),
        color,
        -1
    )

    cv2.addWeighted(
        overlay,
        alpha,
        frame,
        1 - alpha,
        0,
        frame
    )

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        border,
        2,
        cv2.LINE_AA
    )

def draw_progress_bar(frame, x, y, w, h, pct):

    cv2.rectangle(
        frame,
        (x, y),
        (x + w, y + h),
        (40, 40, 40),
        -1
    )

    fw = int(w * max(0.0, min(1.0, pct)))

    cv2.rectangle(
        frame,
        (x, y),
        (x + fw, y + h),
        (0, 255, 120),
        -1
    )

    cv2.rectangle(
        frame,
        (x, y),
        (x + w, y + h),
        (255, 255, 255),
        1
    )

def draw_hud(frame, w, score, level, speed, timer, combo):

    draw_panel(
        frame,
        0,
        0,
        w,
        70,
        (15, 15, 25),
        0.8,
        (0, 255, 255)
    )

    draw_fancy_text(
        frame,
        f"SCORE {score}",
        (20, 45),
        1.0,
        (0, 255, 120)
    )

    draw_fancy_text(
        frame,
        f"LEVEL {level}",
        (250, 45),
        1.0,
        (255, 255, 0)
    )

    draw_fancy_text(
        frame,
        f"SPEED {speed:.1f}",
        (450, 45),
        1.0,
        (255, 120, 0)
    )

    if combo > 1:

        draw_fancy_text(
            frame,
            f"COMBO x{combo}",
            (700, 45),
            1.0,
            (255, 80, 200)
        )

    m, s = divmod(int(max(0, timer)), 60)

    draw_fancy_text(
        frame,
        f"{m:02d}:{s:02d}",
        (w - 180, 45),
        1.0,
        (0, 255, 255)
    )

    draw_progress_bar(
        frame,
        20,
        60,
        w - 40,
        6,
        timer / START_TIMER_SECONDS
    )

def is_pistol_gesture(hl):

    lm = hl.landmark

    return (
        lm[8].y < lm[6].y
        and lm[12].y < lm[10].y
        and lm[16].y > lm[14].y
    )

def load_question_image(name):

    name = str(name).strip()

    base = os.path.splitext(name)[0]

    paths = [
        base + ".jpg",
        base + ".jpeg",
        base + ".png",
        name
    ]

    for p in paths:

        if os.path.exists(p):

            img = cv2.imread(p)

            if img is not None:
                return img

    return None

# =========================================================
# MAIN
# =========================================================

def main():

    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():

        print("Camera not found")
        return

    ok, frame = cap.read()

    if not ok:

        print("Cannot read camera")
        return

    h, w = frame.shape[:2]

    cv2.namedWindow(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN)

    cv2.setWindowProperty(
        WINDOW_NAME,
        cv2.WND_PROP_FULLSCREEN,
        cv2.WINDOW_FULLSCREEN
    )

    mp_hands = mp.solutions.hands

    mp_drawing = mp.solutions.drawing_utils

    hands = mp_hands.Hands(
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )

    # =====================================================
    # GAME OBJECTS
    # =====================================================

    ball = FallingObject(w, h)

    bullets = []
    particles = []

    # =====================================================
    # PLAYER DATA
    # =====================================================

    player_name = ""

    score = 0
    combo = 0
    max_combo = 0
    level = 1

    timer_seconds = START_TIMER_SECONDS

    last_time = time.time()

    current_q = None

    countdown_start = 0

    feedback_msg = ""
    feedback_color = (0, 255, 0)
    feedback_time = 0

    last_shoot_time = 0

    # =====================================================
    # STATES
    # =====================================================

    state = "MENU"

    # =====================================================
    # GAME LOOP
    # =====================================================

    while cap.isOpened():

        ok, frame = cap.read()

        if not ok:
            break

        frame = cv2.flip(frame, 1)

        now = time.time()

        dt = now - last_time

        last_time = now

        cv2.rectangle(frame, (0, 0), (w, h), (0, 0, 0), 8)

        results = hands.process(
            cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        )

        # =================================================
        # MENU
        # =================================================

        if state == "MENU":

            overlay = frame.copy()

            cv2.rectangle(
                overlay,
                (0, 0),
                (w, h),
                (20, 20, 30),
                -1
            )

            cv2.addWeighted(
                overlay,
                0.85,
                frame,
                0.15,
                0,
                frame
            )

            draw_fancy_text(
                frame,
                "MAGIC MOTION QUIZ",
                (w // 2 - 250, 140),
                1.5,
                (0, 255, 255),
                5
            )

            draw_fancy_text(
                frame,
                "ENTER PLAYER NAME :",
                (w // 2 - 240, 260),
                1.1,
                (255, 255, 255),
                3
            )

            cv2.rectangle(
                frame,
                (w // 2 - 250, 300),
                (w // 2 + 250, 370),
                (255, 255, 255),
                2
            )

            draw_fancy_text(
                frame,
                player_name,
                (w // 2 - 220, 350),
                1.2,
                (0, 255, 120),
                3
            )

            draw_fancy_text(
                frame,
                "PRESS ENTER TO CONTINUE",
                (w // 2 - 220, 440),
                1.0,
                (255, 255, 0),
                3
            )

        # =================================================
        # HOW TO PLAY
        # =================================================

        elif state == "HOW_TO_PLAY":

            draw_panel(
                frame,
                40,
                40,
                w - 40,
                h - 40,
                (25, 25, 40),
                0.9,
                (0, 255, 255)
            )

            draw_fancy_text(
                frame,
                "HOW TO PLAY",
                (w // 2 - 220, 100),
                1.8,
                (0, 255, 255),
                4
            )

            instructions = [

                "Point index finger to aim",

                "Make pistol gesture to shoot",

                "Shoot GREEN BALL to answer quiz",

                "Avoid RED BOMB",

                "Correct answer = score increase",

                "Bomb = lose 5 minutes",

                "Combo gives bonus score",

                "Game speed increases over time"
            ]

            y = 180

            for t in instructions:

                draw_fancy_text(
                    frame,
                    "- " + t,
                    (100, y),
                    0.9,
                    (255, 255, 255),
                    2
                )

                y += 55

            draw_fancy_text(
                frame,
                "ITEM GUIDE",
                (w // 2 - 120, 600),
                1.2,
                (255, 255, 0),
                3
            )

            draw_fancy_text(
                frame,
                "GREEN BALL = QUIZ",
                (250, 680),
                1.0,
                (0, 255, 120),
                3
            )

            draw_fancy_text(
                frame,
                "RED BOMB = TIME PENALTY",
                (700, 670),
                1.0,
                (0, 0, 255),
                3
            )

            draw_fancy_text(
                frame,
                "PRESS SPACE TO START",
                (w // 2 - 250, h - 340),
                1.2,
                (0, 255, 255),
                3
            )

        # =================================================
        # PLAYING
        # =================================================

        elif state == "PLAYING":

            timer_seconds -= dt

            level = score // 50 + 1

            if timer_seconds <= 0:

                timer_seconds = 0

                state = "GAME_OVER"

            ball.update(dt)

            draw_hud(
                frame,
                w,
                score,
                level,
                ball.fall_speed,
                timer_seconds,
                combo
            )

            ball.draw(frame)

            for b in bullets[:]:

                b.update(dt)

                b.draw(frame)

                dist = (
                    (b.x - ball.x) ** 2
                    + (b.y - ball.y) ** 2
                )

                if dist < (BALL_RADIUS + 20) ** 2:

                    burst_color = (
                        (0, 0, 255)
                        if ball.type == "bomb"
                        else (0, 255, 255)
                    )

                    for _ in range(30):

                        particles.append(
                            Particle(
                                ball.x,
                                ball.y,
                                burst_color,
                                0.6,
                                5
                            )
                        )

                    if ball.type == "bomb":

                        combo = 0

                        timer_seconds -= BOMB_TIME_PENALTY

                        feedback_msg = "BOMB HIT! -5 MINUTES"
                        feedback_color = (0, 0, 255)

                        if timer_seconds <= 0:
                            timer_seconds = 0

                        state = "FEEDBACK"

                        feedback_time = now

                    else:

                        if QUESTIONS_DATA:

                            state = "COUNTDOWN"

                            countdown_start = now

                        else:

                            feedback_msg = "NO QUESTIONS FOUND"
                            feedback_color = (0, 0, 255)

                            state = "FEEDBACK"

                            feedback_time = now

                    bullets.remove(b)

                elif now - b.spawn_time > 1.2:

                    bullets.remove(b)

        # =================================================
        # COUNTDOWN
        # =================================================

        elif state == "COUNTDOWN":

            elapsed = now - countdown_start

            num = int(COUNTDOWN_DURATION - elapsed) + 1

            overlay = frame.copy()

            cv2.rectangle(
                overlay,
                (0, 0),
                (w, h),
                (0, 0, 0),
                -1
            )

            cv2.addWeighted(
                overlay,
                0.6,
                frame,
                0.4,
                0,
                frame
            )

            draw_fancy_text(
                frame,
                "GET READY!",
                (w // 2 - 200, h // 2 - 50),
                2.0,
                (0, 255, 255),
                4
            )

            draw_fancy_text(
                frame,
                str(num),
                (w // 2 - 40, h // 2 + 100),
                4.0,
                (255, 255, 255),
                6
            )

            if elapsed >= COUNTDOWN_DURATION:

                current_q = random.choice(QUESTIONS_DATA)

                state = "QUESTION"

        # =================================================
        # QUESTION
        # =================================================

        elif state == "QUESTION":

            draw_panel(
                frame,
                30,
                80,
                w - 30,
                h - 30,
                (30, 15, 40),
                0.9,
                (200, 120, 255)
            )

            draw_fancy_text(
                frame,
                current_q["question"],
                (60, 140),
                0.8,
                (255, 255, 255)
            )

            if current_q["type"] == "true_false":

                draw_fancy_text(
                    frame,
                    "TRUE",
                    (w // 4 - 60, h // 2),
                    2.2,
                    (0, 255, 120),
                    5
                )

                draw_fancy_text(
                    frame,
                    "FALSE",
                    (3 * w // 4 - 90, h // 2),
                    2.2,
                    (0, 100, 255),
                    5
                )

            else:

                items = current_q.get(
                    "images",
                    current_q.get("options", [])
                )

                for i in range(min(len(items), 2)):

                    x_pos = 90 if i == 0 else w - 340

                    y_pos = 250

                    img = load_question_image(items[i])

                    if img is not None:

                        img = cv2.resize(img, (250, 180))

                        frame[
                            y_pos:y_pos + 180,
                            x_pos:x_pos + 250
                        ] = img

                        cv2.rectangle(
                            frame,
                            (x_pos, y_pos),
                            (x_pos + 250, y_pos + 180),
                            (255, 255, 255),
                            3
                        )

                    else:

                        draw_fancy_text(
                            frame,
                            str(items[i]).upper(),
                            (x_pos, y_pos + 90),
                            1.0,
                            (255, 255, 255),
                            3
                        )

                draw_fancy_text(
                    frame,
                    "<-- LEFT",
                    (140, 520),
                    1.2,
                    (0, 255, 255),
                    3
                )

                draw_fancy_text(
                    frame,
                    "RIGHT -->",
                    (w - 320, 520),
                    1.2,
                    (0, 255, 255),
                    3
                )

        # =================================================
        # FEEDBACK
        # =================================================

        elif state == "FEEDBACK":

            draw_fancy_text(
                frame,
                feedback_msg,
                (w // 2 - 300, h // 2),
                1.8,
                feedback_color,
                4
            )

            if now - feedback_time > 1.5:

                if timer_seconds <= 0:

                    state = "GAME_OVER"

                else:

                    state = "PLAYING"

                    ball.reset()

        # =================================================
        # GAME OVER
        # =================================================

        elif state == "GAME_OVER":

            overlay = frame.copy()

            cv2.rectangle(
                overlay,
                (0, 0),
                (w, h),
                (0, 0, 0),
                -1
            )

            cv2.addWeighted(
                overlay,
                0.85,
                frame,
                0.15,
                0,
                frame
            )

            draw_fancy_text(
                frame,
                "GAME OVER",
                (w // 2 - 240, 120),
                2.2,
                (0, 0, 255),
                5
            )

            draw_fancy_text(
                frame,
                f"PLAYER : {player_name}",
                (w // 2 - 240, 280),
                1.2,
                (255, 255, 255),
                3
            )

            draw_fancy_text(
                frame,
                f"SCORE : {score}",
                (w // 2 - 240, 360),
                1.2,
                (0, 255, 120),
                3
            )

            draw_fancy_text(
                frame,
                f"MAX COMBO : {max_combo}",
                (w // 2 - 240, 440),
                1.2,
                (255, 255, 0),
                3
            )

            draw_fancy_text(
                frame,
                "PRESS R TO RESTART",
                (w // 2 - 250, 560),
                1.1,
                (0, 255, 255),
                3
            )

            draw_fancy_text(
                frame,
                "PRESS Q TO QUIT",
                (w // 2 - 220, 630),
                1.1,
                (255, 100, 100),
                3
            )

        # =================================================
        # HAND TRACKING
        # =================================================

        if results.multi_hand_landmarks:

            for hl in results.multi_hand_landmarks:

                mp_drawing.draw_landmarks(
                    frame,
                    hl,
                    mp_hands.HAND_CONNECTIONS
                )

                if (
                    is_pistol_gesture(hl)
                    and now - last_shoot_time > SHOOT_COOLDOWN
                ):

                    tx = int(hl.landmark[8].x * w)
                    ty = int(hl.landmark[8].y * h)

                    # =====================================
                    # QUESTION SHOOT
                    # =====================================

                    if state == "QUESTION":

                        is_left = tx < w // 2

                        ans = str(
                            current_q.get("answer", "")
                        ).strip()

                        correct = False

                        if current_q["type"] == "true_false":

                            correct = (
                                (ans == "True" and is_left)
                                or
                                (ans == "False" and not is_left)
                            )

                        else:

                            items = current_q.get(
                                "images",
                                current_q.get("options", [])
                            )

                            if (
                                len(items) >= 1
                                and is_left
                                and ans == str(items[0]).strip()
                            ):
                                correct = True

                            elif (
                                len(items) >= 2
                                and not is_left
                                and ans == str(items[1]).strip()
                            ):
                                correct = True

                        if correct:

                            combo += 1

                            max_combo = max(
                                max_combo,
                                combo
                            )

                            gained = 10 + (combo - 1) * 2

                            score += gained

                            ball.increase_speed()

                            feedback_msg = f"CORRECT! +{gained}"

                            feedback_color = (0, 255, 120)

                        else:

                            combo = 0

                            score = max(0, score - 5)

                            feedback_msg = "WRONG! -5"

                            feedback_color = (0, 0, 255)

                        state = "FEEDBACK"

                        feedback_time = now

                    # =====================================
                    # PLAYING SHOOT
                    # =====================================

                    elif state == "PLAYING":

                        kx = int(hl.landmark[5].x * w)
                        ky = int(hl.landmark[5].y * h)

                        dx = tx - kx
                        dy = ty - ky

                        mag = math.hypot(dx, dy)

                        if mag == 0:
                            mag = 1

                        bullets.append(

                            Bullet(
                                tx,
                                ty,
                                (dx / mag) * BULLET_SPEED,
                                (dy / mag) * BULLET_SPEED
                            )
                        )

                        for _ in range(10):

                            particles.append(
                                Particle(
                                    tx,
                                    ty,
                                    (120, 255, 255),
                                    0.25,
                                    3
                                )
                            )

                    last_shoot_time = now

        # =================================================
        # PARTICLES
        # =================================================

        for p in particles[:]:

            p.update(dt)

            p.draw(frame)

            if p.life <= 0:
                particles.remove(p)

        # =================================================
        # KEYBOARD
        # =================================================

        key = cv2.waitKey(1) & 0xFF

        # MENU INPUT

        if state == "MENU":

            if key == 13:

                if player_name.strip():
                    state = "HOW_TO_PLAY"

            elif key == 8:

                player_name = player_name[:-1]

            elif 32 <= key <= 126:

                if len(player_name) < 15:
                    player_name += chr(key)

        # HOW TO PLAY

        elif state == "HOW_TO_PLAY":

            if key == 32:
                state = "PLAYING"

        # GAME OVER

        elif state == "GAME_OVER":

            if key == ord("r"):

                score = 0
                combo = 0
                max_combo = 0
                level = 1

                timer_seconds = START_TIMER_SECONDS

                bullets.clear()
                particles.clear()

                ball.fall_speed = BASE_FALL_SPEED

                ball.reset()

                state = "PLAYING"

            elif key == ord("q"):
                break

        # QUIT

        if key == ord("q"):
            break

        cv2.imshow(WINDOW_NAME, frame)

    cap.release()

    cv2.destroyAllWindows()

# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()