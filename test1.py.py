import cv2
import mediapipe as mp
import random
import time
import json
import os

# ---------------- CONFIGURATION ----------------
CAMERA_INDEX = 0
WINDOW_NAME = "⭐ MAGIC MOTION QUIZ ⭐"
START_TIMER_SECONDS = 10 * 60
BALL_RADIUS = 35
BULLET_SPEED = 500.0
BULLET_COLOR = (0, 255, 255)
SHOOT_COOLDOWN = 0.5
COUNTDOWN_DURATION = 3

BALL_IMAGE_PATH = "ball.jpg"
BOMB_IMAGE_PATH = "bomb.jpg"
BOMB_CHANCE = 0.25
BOMB_TIME_PENALTY = 5 * 60

# ---------------- Load Questions ----------------
QUESTIONS_DATA = []
try:
    with open("questions.json", "r") as f:
        data = json.load(f)
        QUESTIONS_DATA = data["questions"]
except Exception as e:
    print(f"JSON Error: {e}")

# ---------------- Classes ----------------
class Bullet:
    def __init__(self, x, y, dx, dy):
        self.x, self.y = float(x), float(y)
        self.dx, self.dy = float(dx), float(dy)
        self.spawn_time = time.time()

class FallingObject:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ball_img = cv2.imread(BALL_IMAGE_PATH, cv2.IMREAD_UNCHANGED)
        self.bomb_img = cv2.imread(BOMB_IMAGE_PATH, cv2.IMREAD_UNCHANGED)

        if self.ball_img is None:
            print("ball.jpg not found")
        if self.bomb_img is None:
            print("bomb.jpg not found")

        self.reset()

    def reset(self):
        self.x = random.randint(80, self.w - 80)
        self.y = -80

        if random.random() < BOMB_CHANCE:
            self.type = "bomb"
            self.img = self.bomb_img
        else:
            self.type = "ball"
            self.img = self.ball_img

    def update(self, level=1):
        self.y += 5 + level
        if self.y > self.h + 80:
            self.reset()

    def draw(self, frame):
        if self.img is not None:
            img = cv2.resize(self.img, (80, 80))

            x1 = int(self.x - 40)
            y1 = int(self.y - 40)
            x2 = x1 + 80
            y2 = y1 + 80

            if x1 < 0 or y1 < 0 or x2 > self.w or y2 > self.h:
                return

            if len(img.shape) == 3 and img.shape[2] == 4:
                alpha = img[:, :, 3] / 255.0
                for c in range(3):
                    frame[y1:y2, x1:x2, c] = (
                        alpha * img[:, :, c] +
                        (1 - alpha) * frame[y1:y2, x1:x2, c]
                    )
            else:
                frame[y1:y2, x1:x2] = img[:, :, :3]
        else:
            color = (0, 0, 255) if self.type == "bomb" else (0, 255, 0)
            cv2.circle(frame, (int(self.x), int(self.y)), BALL_RADIUS, color, -1)

# ---------------- Helper Functions ----------------
def draw_fancy_text(img, text, pos, size=1.0, color=(255, 255, 255), thickness=2):
    x, y = pos
    cv2.putText(img, str(text), (x + 2, y + 2),
                cv2.FONT_HERSHEY_DUPLEX, size, (0, 0, 0),
                thickness + 2, cv2.LINE_AA)
    cv2.putText(img, str(text), (x, y),
                cv2.FONT_HERSHEY_DUPLEX, size, color,
                thickness, cv2.LINE_AA)

def is_pistol_gesture(hl):
    lm = hl.landmark
    return lm[8].y < lm[6].y and lm[12].y < lm[10].y and lm[16].y > lm[14].y

def load_question_image(name):
    name = str(name).strip()
    base = os.path.splitext(name)[0]

    possible_paths = [
        base + ".jpg",
        base + ".JPG",
        base + ".jpeg",
        base + ".JPEG",
        name
    ]

    for path in possible_paths:
        if os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                print("Loaded answer image:", path)
                return img

    print("FAILED to load answer image:", name)
    return None

# ---------------- MAIN ----------------
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
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    hands = mp_hands.Hands(min_detection_confidence=0.7,
                           min_tracking_confidence=0.7)

    ball = FallingObject(w, h)
    bullets = []
    score = 0
    level = 1

    timer_seconds = START_TIMER_SECONDS
    last_time = time.time()

    state = "PLAYING"
    current_q = None
    countdown_start = 0

    feedback_msg = ""
    feedback_color = (0, 255, 0)
    feedback_time = 0
    last_shoot_time = 0

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)

        dt = time.time() - last_time
        last_time = time.time()

        if state == "PLAYING":
            timer_seconds -= dt
            level = score // 50 + 1
            ball.update(level)

            if timer_seconds <= 0:
                timer_seconds = 0
                feedback_msg = "GAME OVER"
                feedback_color = (0, 0, 255)
                state = "FEEDBACK"
                feedback_time = time.time()

        results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        # ---------------- HUD ----------------
        cv2.rectangle(frame, (0, 0), (w, 60), (40, 40, 40), -1)
        draw_fancy_text(frame, f"SCORE: {score}", (20, 40), 1.0, (0, 255, 0))
        draw_fancy_text(frame, f"LEVEL: {level}", (220, 40), 1.0, (255, 255, 0))

        m, s = divmod(int(max(0, timer_seconds)), 60)
        draw_fancy_text(frame, f"TIME: {m:02d}:{s:02d}",
                        (w - 200, 40), 1.0, (0, 255, 255))

        # ---------------- PLAYING ----------------
        if state == "PLAYING":
            ball.draw(frame)

            for b in bullets[:]:
                b.x += b.dx * dt
                b.y += b.dy * dt

                cv2.circle(frame, (int(b.x), int(b.y)), 10, BULLET_COLOR, -1)

                if ((b.x - ball.x) ** 2 + (b.y - ball.y) ** 2) < (BALL_RADIUS + 20) ** 2:
                    if ball.type == "bomb":
                        timer_seconds -= BOMB_TIME_PENALTY
                        feedback_msg = "BOMB HIT! -5 MINUTES"
                        feedback_color = (0, 0, 255)
                        state = "FEEDBACK"
                        feedback_time = time.time()

                        if timer_seconds <= 0:
                            timer_seconds = 0
                            feedback_msg = "GAME OVER"

                    else:
                        if QUESTIONS_DATA:
                            state = "COUNTDOWN"
                            countdown_start = time.time()
                        else:
                            feedback_msg = "NO QUESTIONS FOUND"
                            feedback_color = (0, 0, 255)
                            state = "FEEDBACK"
                            feedback_time = time.time()

                    bullets.remove(b)

                elif time.time() - b.spawn_time > 1.2:
                    bullets.remove(b)

        # ---------------- COUNTDOWN ----------------
        elif state == "COUNTDOWN":
            elapsed = time.time() - countdown_start
            num = int(COUNTDOWN_DURATION - elapsed) + 1

            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
            frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

            draw_fancy_text(frame, "GET READY!",
                            (w // 2 - 140, h // 2 - 50),
                            2.0, (0, 255, 255), 4)

            draw_fancy_text(frame, str(num),
                            (w // 2 - 30, h // 2 + 80),
                            4.0, (255, 255, 255), 6)

            if elapsed >= COUNTDOWN_DURATION:
                current_q = random.choice(QUESTIONS_DATA)
                state = "QUESTION"

        # ---------------- QUESTION ----------------
        elif state == "QUESTION":
            overlay = frame.copy()
            cv2.rectangle(overlay, (40, 70), (w - 40, h - 40), (60, 30, 30), -1)
            frame = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)

            draw_fancy_text(frame, current_q["question"],
                            (60, 120), 0.7, (255, 255, 255))

            if current_q["type"] == "true_false":
                draw_fancy_text(frame, "TRUE",
                                (w // 4 - 50, 350),
                                2.0, (0, 255, 0), 4)
                draw_fancy_text(frame, "FALSE",
                                (3 * w // 4 - 70, 350),
                                2.0, (0, 0, 255), 4)

            else:
                items = current_q.get("images", current_q.get("options", []))

                for i in range(min(len(items), 2)):
                    x_pos = 90 if i == 0 else w - 340
                    y_pos = 250

                    img = load_question_image(items[i])

                    if img is not None:
                        img = cv2.resize(img, (250, 180))
                        frame[y_pos:y_pos + 180, x_pos:x_pos + 250] = img
                        cv2.rectangle(frame,
                                      (x_pos, y_pos),
                                      (x_pos + 250, y_pos + 180),
                                      (255, 255, 255), 3)
                    else:
                        draw_fancy_text(frame, str(items[i]).upper(),
                                        (x_pos, y_pos + 90),
                                        1.0, (255, 255, 255), 3)

                draw_fancy_text(frame, "LEFT",
                                (140, 480), 1.2, (0, 255, 255), 3)
                draw_fancy_text(frame, "RIGHT",
                                (w - 280, 480), 1.2, (0, 255, 255), 3)

        # ---------------- FEEDBACK ----------------
        elif state == "FEEDBACK":
            draw_fancy_text(frame, feedback_msg,
                            (w // 2 - 230, h // 2),
                            1.7, feedback_color, 4)

            if time.time() - feedback_time > 1.5:
                if timer_seconds <= 0:
                    break

                state = "PLAYING"
                ball.reset()

        # ---------------- HAND TRACKING ----------------
        if results.multi_hand_landmarks:
            for hl in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)

                if is_pistol_gesture(hl) and (time.time() - last_shoot_time > SHOOT_COOLDOWN):
                    tx = int(hl.landmark[8].x * w)
                    ty = int(hl.landmark[8].y * h)

                    if state == "QUESTION":
                        is_left = tx < w // 2
                        ans = str(current_q.get("answer", "")).strip()
                        correct = False

                        if current_q["type"] == "true_false":
                            correct = (ans == "True" and is_left) or (ans == "False" and not is_left)

                        else:
                            items = current_q.get("images", current_q.get("options", []))

                            if len(items) >= 1 and is_left and ans == str(items[0]).strip():
                                correct = True
                            elif len(items) >= 2 and not is_left and ans == str(items[1]).strip():
                                correct = True

                        if correct:
                            score += 10
                            feedback_msg = "CORRECT! +10"
                            feedback_color = (0, 255, 0)
                        else:
                            score -= 5
                            feedback_msg = "WRONG! -5"
                            feedback_color = (0, 0, 255)

                        state = "FEEDBACK"
                        feedback_time = time.time()

                    elif state == "PLAYING":
                        kx = int(hl.landmark[5].x * w)
                        ky = int(hl.landmark[5].y * h)

                        dx = tx - kx
                        dy = ty - ky
                        mag = (dx ** 2 + dy ** 2) ** 0.5 or 1

                        bullets.append(
                            Bullet(tx, ty,
                                   (dx / mag) * BULLET_SPEED,
                                   (dy / mag) * BULLET_SPEED)
                        )

                    last_shoot_time = time.time()

        cv2.imshow(WINDOW_NAME, frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

# ---------------- RUN ----------------
if __name__ == "__main__":
    main()