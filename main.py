import sys
import os
import cv2
import time
from datetime import datetime

from PyQt5.QtCore import QPropertyAnimation, pyqtProperty, QEasingCurve, Qt, QTimer, QRect, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedLayout,
    QGraphicsOpacityEffect,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame
)
from PyQt5.QtGui import QPixmap, QPen, QColor, QPainter
from PyQt5.QtGui import QFontDatabase, QFont
import numpy as np
from scipy.spatial import Voronoi
from datetime import date, timedelta
import threading
import random
import sys
import os

ON_RPI = False
try:
    import pigpio
    pi = pigpio.pi()
    ON_RPI = pi.connected
except (ImportError, RuntimeError):
    pi = None
    ON_RPI = False

from PyQt5.QtGui import QCursor



if ON_RPI:
    GPIO_INPUT_PIN = 21
    PWM_PIN = 15  # Use GPIO12 for PWM
    pi.set_PWM_frequency(PWM_PIN, 1000)  # 1kHz
    pi.set_PWM_dutycycle(PWM_PIN, 0)     # Start with 0% duty cycle
    pi.set_mode(GPIO_INPUT_PIN, pigpio.INPUT)
    pi.set_pull_up_down(GPIO_INPUT_PIN, pigpio.PUD_UP)  # <-- This enables the pull-up
else:
    GPIO_INPUT_PIN = None
    PWM_PIN = None

os.environ["QT_QPA_PLATFORMTHEME"] = "fusion"

latest_emotion = None
latest_mood = None

class StatisticsChart(QWidget):
    day_clicked = pyqtSignal(int)  # index in self.data
    def __init__(self, parent=None, start_date=None, title_label=None):
        super().__init__(parent)
        self.setMinimumSize(800, 400)
        self.setMaximumSize(800, 400)
        self.setStyleSheet("background: transparent;")
        # Use float values for more precise mood positions
        self.data = [
            2.0, 3.0, 4.0, 2.5, 3.7, 1.2, 2.8, 3.3, 2.1, 1.0, 3.5, 4.0, 2.2, 2.9, 3.0, 1.7, 2.0, 4.0, 3.1, 2.6, 1.0, 2.4, 3.2, 4.0, 2.0, 1.5, 3.0, 2.3
        ]
        self.window_size = 7
        self.num_windows = (len(self.data) + self.window_size - 1) // self.window_size
        # Start at the latest week
        self.window_start = max(0, len(self.data) - self.window_size)
        self._drag_start_x = None
        self.start_date = start_date or date(2024, 4, 1)  # Default: April 1, 2024
        self.title_label = title_label
        self.update_title()

    def update_title(self):
        # Calculate the date range for the current window
        start = self.start_date + timedelta(days=self.window_start)
        end = self.start_date + timedelta(days=min(self.window_start + self.window_size - 1, len(self.data) - 1))
        months = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
        title = f"MEDIA DIARIA ({start.day} - {end.day}, {months[end.month-1]})"
        if self.title_label:
            self.title_label.setText(title)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Colors and pens
        orange = QColor(217, 134, 86)
        grid_pen = QPen(QColor(180, 120, 80, 100))
        grid_pen.setWidth(2)
        line_pen = QPen(orange)
        line_pen.setWidth(2)
        dot_brush = orange

        # Margins
        left = 40
        right = 20
        top = 10
        bottom = 90

        # Draw horizontal grid lines and labels
        levels = ["MUY BIEN", "BIEN", "NORMAL", "MAL", "MUY MAL"]
        for i, label in enumerate(levels):
            y = top + i * (h - top - bottom) / 4
            painter.setPen(QPen(QColor(180, 120, 80, 100), 1))
            painter.drawLine(10, int(y), w - right, int(y))
            painter.setPen(QColor(180, 180, 180) if i in [0, 4] else QColor(255, 255, 255))
            painter.setFont(QFont("Jost", 20))
            painter.drawText(10, int(y) + 16, label)

        # Draw line and dots for visible window
        points = []
        visible_data = self.data[self.window_start:self.window_start + self.window_size]
        for i, value in enumerate(visible_data):
            x = left + i * (w - left - right) / (self.window_size - 1)
            # Use float value for y position
            y = top + (4 - float(value)) * (h - top - bottom) / 4
            points.append((x, y))
        painter.setPen(line_pen)
        for i in range(len(points) - 1):
            painter.drawLine(int(points[i][0]), int(points[i][1]), int(points[i+1][0]), int(points[i+1][1]))
        painter.setBrush(dot_brush)
        for x, y in points:
            painter.drawEllipse(int(x) - 8, int(y) - 8, 16, 16)

        # Draw day labels
        days = ["L", "M", "X", "J", "V", "S", "D"]
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Jost", 18))
        for i, day in enumerate(days):
            x = left + i * (w - left - right) / (self.window_size - 1)
            painter.drawText(int(x) - 16, h - 65, 32, 40, Qt.AlignCenter, day)

        # Draw navigation dots (and store clickable areas)
        self.dot_rects = []
        dot_y = h - 20
        dot_x0 = w // 2 - (self.num_windows * 15)
        for i in range(self.num_windows):
            rect = QRect(dot_x0 + i * 30, dot_y, 10, 10)
            self.dot_rects.append(rect)
            if i == self.window_start // self.window_size:
                painter.setBrush(QColor(255, 255, 255))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(rect)
            else:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.drawEllipse(rect)

    def scroll_left(self):
        if self.window_start - self.window_size >= 0:
            self.window_start -= self.window_size
            self.update()
            self.update_title()

    def scroll_right(self):
        if self.window_start + self.window_size < len(self.data):
            self.window_start += self.window_size
            self.update()
            self.update_title()

    def mousePressEvent(self, event):
        self._drag_start_x = event.x()
        # Check if a dot was clicked
        for i, rect in enumerate(getattr(self, 'dot_rects', [])):
            if rect.contains(event.pos()):
                self.window_start = i * self.window_size
                self.update()
                self.update_title()
                return
        # Check if a day was clicked
        left = 120
        right = 40
        w = self.width()
        x_positions = [
            left + i * (w - left - right) / (self.window_size - 1)
            for i in range(self.window_size)
        ]
        for i, x in enumerate(x_positions):
            if abs(event.x() - x) < 10:  # 30px tolerance
                global_idx = self.window_start + i
                if global_idx < len(self.data):
                    self.day_clicked.emit(global_idx)
                return

    def mouseMoveEvent(self, event):
        if self._drag_start_x is not None:
            dx = event.x() - self._drag_start_x
            threshold = 60
            if dx > threshold:
                self.scroll_left()
                self._drag_start_x = event.x()
            elif dx < -threshold:
                self.scroll_right()
                self._drag_start_x = event.x()

    def mouseReleaseEvent(self, event):
        self._drag_start_x = None

class VoronoiWidget(QWidget):
    def __init__(self, parent=None, num_points=400, edges_per_tick=100):
        self.r = 217
        self.g = 134
        self.b = 86
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000;")
        self.setFixedSize(800, 480)
        
        # Initialize data structures
        self.points = []
        self.shown_edges = set()
        self.all_edges = []
        self.edge_graph = {}
        self.edge_lookup = {}
        self.visited_vertices = set()
        self.edges_to_add = []
        self.vor = None
        self.edges_per_tick = edges_per_tick  # Now configurable
        
        # Generate random points
        margin = 0
        width = self.width()
        height = self.height()
        x_coords = np.random.uniform(margin, width - margin, num_points)
        y_coords = np.random.uniform(margin, height - margin, num_points)
        self.points = np.column_stack((x_coords, y_coords))
        
        # Calculate Voronoi diagram
        self.vor = Voronoi(self.points)
        
        # Pre-compute edges and build graph
        self.precompute_edges()
        
        # Setup timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.add_edge)
        self.timer.setInterval(1)

    def precompute_edges(self):
        """Pre-compute all edges and build graph structure"""
        vertices = self.vor.vertices
        for simplex in self.vor.ridge_vertices:
            if -1 not in simplex:
                v1, v2 = simplex
                edge = ((vertices[v1][0], vertices[v1][1]), 
                       (vertices[v2][0], vertices[v2][1]))
                self.all_edges.append(edge)
                
                # Build graph and edge lookup
                self.edge_graph.setdefault(v1, []).append((v2, edge))
                self.edge_graph.setdefault(v2, []).append((v1, edge))
                self.edge_lookup[edge] = [(v1, v2, edge)]
        
        # Find leftmost vertex
        self.start_vertex = min(self.edge_graph.keys(), 
                              key=lambda v: vertices[v][0])

    def add_adjacent_edges(self, vertex):
        """Add all edges connected to a vertex to the queue"""
        if vertex in self.edge_graph:
            for next_vertex, edge in self.edge_graph[vertex]:
                if edge not in self.shown_edges and edge not in self.edges_to_add:
                    self.edges_to_add.append(edge)

    def add_edge(self):
        """Add multiple edges at a time for faster animation"""
        count = 0
        while self.edges_to_add and count < self.edges_per_tick:
            edge = self.edges_to_add.pop(0)
            self.shown_edges.add(edge)
            # Add connected edges
            if edge in self.edge_lookup:
                for v1, v2, _ in self.edge_lookup[edge]:
                    if v1 not in self.visited_vertices:
                        self.visited_vertices.add(v1)
                        self.add_adjacent_edges(v1)
                    if v2 not in self.visited_vertices:
                        self.visited_vertices.add(v2)
                        self.add_adjacent_edges(v2)
            count += 1
        self.update()
        if not self.edges_to_add:
            self.timer.stop()

    def paintEvent(self, event):
        """Paint the current state of the Voronoi diagram"""
        if not self.vor:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        edge_pen = QPen(QColor(self.r, self.g, self.b))
        edge_pen.setWidthF(0.5)
        painter.setPen(edge_pen)
        
        for (x1, y1), (x2, y2) in self.shown_edges:
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    def start_animation(self):
        """Start the edge animation"""
        self.edges_to_add = self.all_edges.copy()
        self.shown_edges = set()
        self.visited_vertices = set()
        print(f"Starting animation with {len(self.edges_to_add)} edges")
        self.timer.start()

class FadeWidget(QWidget):
    def __init__(self, child_widget):
        super().__init__()
        self._opacity = 1.0
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: #000000;")
        

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(child_widget)

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, value):
        self._opacity = value
        self.effect.setOpacity(value)

    opacity = pyqtProperty(float, get_opacity, set_opacity)

class MainScreen(QMainWindow):
    def __init__(self):
        super().__init__()


        self.setWindowTitle("Decentralized Widget Demo")

        if ON_RPI:
            from no_graphic import CameraFacialEmotionDetector
            self.facial_detector = CameraFacialEmotionDetector()
            self.latest_emotion = None
            self.latest_mood = None
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.showFullScreen()
            self.setCursor(Qt.BlankCursor)
            QApplication.setOverrideCursor(Qt.BlankCursor)
        else:
            from internet_fer import CameraFacialEmotionDetector
            self.facial_detector = CameraFacialEmotionDetector()
            self.latest_emotion = None
            self.latest_mood = None
            self.resize(800, 480)  # Or any size you prefer for Mac
            self.setWindowFlags(Qt.Window)
            self.setCursor(Qt.ArrowCursor)
            QApplication.setOverrideCursor(Qt.ArrowCursor)
        self._scan_thread = None
        self._scan_running = False
        self.black_overlay = QWidget(self)
        self.black_overlay.setStyleSheet("background-color: black;")
        self.black_overlay.hide()
        self.black_overlay.setGeometry(0, 0, 800, 480)  # Adjust to your screen size
        self.black_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.current = 0  # Start with the first widget
        self.phraseIndex = random.randint(0,4)
        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #000000;")
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)


        self._gpio_timer = QTimer(self)
        self._gpio_timer.timeout.connect(self._check_gpio_input)
        self._gpio_timer.start(100)  # Check every 100ms

        self.stack = QStackedLayout()
        main_layout.addLayout(self.stack)

        self.fade_widgets = []
        self._animations = []
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._auto_switch)

        # Add widgets
        self.create_initial_widget(next_widget_index=1)                         #0
        self.create_widget1(next_widget_index=2)                     #1 
        self.create_widget2(next_widget_index1=3, next_widget_index2=8, next_widget_index3=9) #2
        self.create_show_face_widget(next_widget_index=4)            #3
        self.create_scan_face_countdown_widget(next_widget_index=5)     #4
        self.create_deteced_emotion_widget(next_widget_index1=6, next_widget_index2=4)      #5
        self.create_describe_emotion_widget(next_widget_index=7) #6
        self.create_cause_emotion_widget(next_widget_index=10) #7
        self.create_statistics_widget(next_widget_index=2) #8
        self.create_contacts_widget(next_widget_index=2) # 9
        self.create_send_to_contacts_widget(next_widget_index_si=2, next_widget_index_no=2) # 10

       # self.create_day_details_widget(next_widget_index=9) #10
        

        self._detection_running = True
        self._detection_thread = threading.Thread(target=self._continuous_face_detection, daemon=True)
        self._detection_thread.start()

        # Set the first widget as visible
        self.stack.setCurrentWidget(self.fade_widgets[0])
        self.fade_widgets[0].set_opacity(1)

        # Start the timer if the first widget has auto transition
        self._start_auto_timer_for_current()
    # def resizeEvent(self, event):
    #     super().resizeEvent(event)
    #     self.black_overlay.setGeometry(0, 0, self.width(), self.height())
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.timeout.connect(self.on_long_press)
        self._long_press_threshold = 5000  # milliseconds

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._long_press_timer.start(self._long_press_threshold)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._long_press_timer.stop()
        super().mouseReleaseEvent(event)

    def on_long_press(self):
        print("Long press detected on main window!")
        os._exit(0)
        # You can trigger any action here, e.g.:
        # self.fade_to(self.current, 0)  # Go to first widget, etc.
    def _check_gpio_input(self):
        if ON_RPI:
            if pi.read(GPIO_INPUT_PIN) == 0:
                print("[DEBUG] GPIO input detected, toggling black overlay.")
                pi.set_PWM_dutycycle(PWM_PIN, 0)

                self.black_overlay.show()
                self.black_overlay.raise_()  # <-- Ensure overlay is on top

            else:
                print("[DEBUG] GPIO input not detected, hiding black overlay.")
                if self.black_overlay.isVisible():
                    self.phraseIndex = random.randint(0,4)
                    self.black_overlay.hide()
                    self.reset_program()
    def reset_program(self):
        # Reset to the first screen
        self.current = 0
        self.phraseIndex = random.randint(0,4)

        self.stack.setCurrentWidget(self.fade_widgets[0])
        self.fade_widgets[0].set_opacity(1)
        self._start_auto_timer_for_current()

    def _continuous_face_detection(self):
        print("[DEBUG] Starting continuous face detection thread...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[DEBUG] Could not open the camera for continuous detection.")
            return
        try:
            while self._detection_running:
                # Flush buffer for freshest frame
                for _ in range(5):
                    cap.read()
                ret, frame = cap.read()
                if not ret:
                    continue
                frame = cv2.resize(frame, (320, 240))
                faces = self.facial_detector.detect_faces(frame)
                if faces:
                    biggest = max(faces, key=lambda f: f['w'] * f['h'])
                    x, y, w, h = biggest['x'], biggest['y'], biggest['w'], biggest['h']
                    face_roi = frame[y:y+h, x:x+w]
                    emotions = self.facial_detector.process_face(face_roi)
                    mood = self.facial_detector.classify_mood(
                        emotions['Happy'], emotions['Normal'], emotions['Sad']
                    )
                    self.latest_emotion = emotions
                    self.latest_mood = mood
                # else:  # Do NOT overwrite latest_emotion/latest_mood if no face detected
                time.sleep(0.5)  # Adjust for CPU usage
        finally:
            print("[DEBUG] Releasing camera for continuous detection...")
            cap.release()

    def create_initial_widget(self, next_widget_index):
        """
        Creates the initial widget with an image and auto transition to widget1.
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add an image to the initial widget
        label = QLabel()
        label.setPixmap(QPixmap("cupra.png").scaled(370, 170, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        # Store transition behavior
        fade_widget.auto = True
        fade_widget.duration = 3000  # Auto transition after 3 seconds
        fade_widget.next_widget_index = next_widget_index

    def create_widget1(self, next_widget_index):
        # Add these to your widget class

        phrases = [
            "LO QUE SIENTES\nIMPORTA",
            "ESCÚCHATE,\nCADA DÍA\nCUENTA",
            "SENTIR\nNO ES MALO,\nES HUMANO",
            "PARA,\nRESPIRA,\nSIENTE",
            "APRENDE\nA ENTENDERTE"
        ]
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(0)

        # Store label as instance variable
        self.widget1_label = QLabel("", alignment=Qt.AlignCenter)
        self.widget1_label.setStyleSheet(f"color: white; font-size: 50px; font-family: '{jostLight}';")
        layout.addWidget(self.widget1_label)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        # Set a new random phrase every time the widget is shown
        def set_random_phrase():
            self.widget1_label.setText(random.choice(phrases))
        fade_widget.visibilityChanged = set_random_phrase

        fade_widget.auto = True
        fade_widget.duration = 2000  # Auto transition after 2 seconds
        fade_widget.next_widget_index = next_widget_index
    def create_widget2(self, next_widget_index1, next_widget_index2, next_widget_index3):
        
        """
        Creates the second widget with three options, each with an orange underline (text-decoration).
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(8)
        label1 = QLabel("ENTENDER TU ESTADO DE ÁNIMO\nES CLAVE PARA PODER REFLEXIONAR SOBRE\nLO QUE PODRÍA INFLUIR EN TU\nBIENESTAR EMOCIONAL.", alignment=Qt.AlignLeft)
        font_path1 = os.path.join(os.path.dirname(__file__), "Jost-ExtraLight.ttf")
        font_id1 = QFontDatabase.addApplicationFont(font_path1)
        if font_id1 == -1:
            print("Failed to load font: Jost-ExtraLight.ttf")
        else:
            jostExtraLight = QFontDatabase.applicationFontFamilies(font_id1)[0]
            print("Loaded font family:", jostExtraLight)

        label1.setStyleSheet(f"color: white; font-size: 35px; font-family: 'Jost'; font-weight: 200;")
        layout.addWidget(label1)

        # --- Option 1: ESCANEAR ESTADO EMOCIONAL ---
        button = QPushButton("ESCANEAR ESTADO EMOCIONAL")
        button.setStyleSheet("""
            QPushButton {
                background-color: #000;
                color: white;
                font-size: 30px;
                font-family: 'Jost';
                font-weight: 170;
                border: none;
                border-bottom: 1px solid orange;
                padding-bottom: 5px;
            }
        """)
        button.setFixedHeight(36)
        layout.addWidget(button, alignment=Qt.AlignLeft)
        layout.addSpacing(18)  # Add spacing between buttons

        # --- Option 2: VER ESTADÍSTICAS DEL ESTADO EMOCIONAL ---
        button2 = QPushButton("VER ESTADÍSTICAS DEL ESTADO EMOCIONAL")
        button2.setStyleSheet("""
            QPushButton {
                background-color: #000;
                color: white;
                font-size: 30px;
                font-family: 'Jost';
                font-weight: 170;
                border: none;
                border-bottom: 1px solid orange;
                padding-bottom: 5px;
            }
        """)
        button2.setFixedHeight(36)
        layout.addWidget(button2, alignment=Qt.AlignLeft)
        layout.addSpacing(18)  # Add spacing between buttons

        # --- Option 3: VER CONTACTOS ---
        button3 = QPushButton("VER CONTACTOS")
        button3.setStyleSheet("""
            QPushButton {
                background-color: #000;
                color: white;
                font-size: 30px;
                font-family: 'Jost';
                font-weight: 170;
                border: none;
                border-bottom: 1px solid orange;
                padding-bottom: 5px;
            }
        """)
        button3.setFixedHeight(36)
        layout.addWidget(button3, alignment=Qt.AlignLeft)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        # Connect button for manual transition
        button.clicked.connect(lambda: self.fade_to(self.current, next_widget_index1))
        button2.clicked.connect(lambda: self.fade_to(self.current, next_widget_index2))
        button3.clicked.connect(lambda: self.fade_to(self.current, next_widget_index3))

        # Store transition behavior
        fade_widget.auto = False

    def create_contacts_widget(self, next_widget_index):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Fullscreen image (replace 'contacts.png' with your image file)
        image_label = QLabel()
        image_label.setPixmap(QPixmap("contactos.png").scaled(800, 440, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(image_label)

        # Cross button (top-right, overlay style)
        cross_btn = QPushButton("✕", widget)
        cross_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background: rgba(0,0,0,0.5);
                border: none;
                font-size: 36px;
                font-family: 'Jost';
                font-weight: 200;
                padding: 0 12px;
            }
            QPushButton:hover {
                color: orange;
            }
        """)
        cross_btn.setFixedSize(40, 40)
        cross_btn.move(740, 10)  # Position at top-right (800-48-12, 10)
        cross_btn.raise_()
        cross_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index))

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)
        return fade_widget

    def create_share_contacts_widget(self, next_widget_index):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("¿CON QUIÉN QUIERES COMPARTIRLO?")
        title.setStyleSheet("color: white; font-size: 20px; font-family: 'Jost'; font-weight: 200;")
        title.setAlignment(Qt.AlignLeft)
        layout.addWidget(title)
        layout.addSpacing(8)

        # Example contacts list with checkboxes
        contacts = ["Mamá", "Papá", "Amigo 1", "Amiga 2", "Psicóloga"]
        self.selected_contacts = set()
        for contact in contacts:
            btn = QPushButton(contact)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #000;
                    color: #ccc;
                    font-size: 18px;
                    font-family: 'Jost';
                    font-weight: 200;
                    border: 2px solid #444;
                    border-radius: 12px;
                    margin-bottom: 10px;
                }
                QPushButton:checked {
                    background-color: orange;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda checked, c=contact: self.selected_contacts.add(c) if checked else self.selected_contacts.discard(c))
            layout.addWidget(btn)
            layout.addSpacing(2)

        layout.addStretch()

        # GUARDAR button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        guardar_btn = QPushButton("GUARDAR")
        guardar_btn.setStyleSheet("""
            background-color: #000;
            color: white;
            font-size: 18px;
            font-family: 'Jost';
            font-weight: 100;
            border: none;
        """)
        guardar_btn.setFixedHeight(28)
        button_container = QVBoxLayout()
        button_container.setSpacing(0)
        button_container.setContentsMargins(0, 0, 0, 0)
        button_container.addWidget(guardar_btn)
        underline = QFrame()
        underline.setFrameShape(QFrame.HLine)
        underline.setFrameShadow(QFrame.Plain)
        underline.setStyleSheet("background-color: orange;")
        underline.setFixedHeight(2)
        button_container.addWidget(underline)
        button_layout.addLayout(button_container)
        layout.addLayout(button_layout)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        guardar_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index))
        return fade_widget

    # --- In __init__ or where you add widgets, update the indices ---
    # Example:
    # --- At the end of create_send_to_contacts_widget, after user says "SI", go to share contacts page ---
    
    def create_show_face_widget(self, next_widget_index):
        """
        Creates the widget that shows the face with a button to go back.
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)

        label = QLabel("MUESTRA CON TU\nROSTRO CÓMO TE\nSIENTES", alignment=Qt.AlignCenter)
        label.setStyleSheet("color: white; font-size: 50px; font-family: 'Jost'; font-weight: 200;")
        layout.addWidget(label, alignment=Qt.AlignCenter)


        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        # Connect button for manual transition
        fade_widget.auto = True
        fade_widget.duration = 4000  # Auto transition after 3 seconds
        fade_widget.next_widget_index = next_widget_index

   # Add this import at the top if not present

    def scan_and_detect_emotion(self):
        """
        This method runs in a thread and uses the same logic as no_graphic.py
        to get the freshest frame and detect emotion.
        """
        print("[DEBUG] Opening camera for scan...")
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if not cap.isOpened():
            print("[DEBUG] Could not open the camera (try sudo or check camera connection)")
            self.latest_emotion = None
            self.latest_mood = None
            return

        try:
            print("[DEBUG] Flushing camera buffer...")
            for _ in range(10):
                cap.read()
            print("[DEBUG] Capturing frame...")
            ret, frame = cap.read()
            if not ret:
                print("[DEBUG] Failed to capture frame. Exiting scan.")
                self.latest_emotion = None
                self.latest_mood = None
                return

            frame = cv2.resize(frame, (320, 240))
            faces = self.facial_detector.detect_faces(frame)
            if faces:
                biggest = max(faces, key=lambda f: f['w'] * f['h'])
                x, y, w, h = biggest['x'], biggest['y'], biggest['w'], biggest['h']
                print(f"[DEBUG] Biggest face at (x: {x}, y: {y}, w: {w}, h: {h})")
                face_roi = frame[y:y+h, x:x+w]
                emotions = self.facial_detector.process_face(face_roi)
                mood = self.facial_detector.classify_mood(emotions['Happy'], emotions['Normal'], emotions['Sad'])
                timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                print(f"Timestamp: {timestamp}")
                print(f"Face at (x: {x}, y: {y}, w: {w}, h: {h})")
                print(f"  Mood: {mood}")
                print(f"  Happy: {emotions['Happy']*100:.2f}%")
                print(f"  Normal: {emotions['Normal']*100:.2f}%")
                print(f"  Sad: {emotions['Sad']*100:.2f}%")
                self.latest_emotion = emotions
                self.latest_mood = mood
            else:
                print("[DEBUG] No faces detected in this frame.")
                self.latest_emotion = None
                self.latest_mood = None
        finally:
            print("[DEBUG] Releasing camera...")
            cap.release()

    def create_scan_face_countdown_widget(self, next_widget_index):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)

        label = QLabel("ESCANEANDO\nEMOCIONES", alignment=Qt.AlignCenter)
        label.setStyleSheet("color: white; font-size: 50px; font-family: 'Jost'; font-weight: 200;")
        layout.addWidget(label, alignment=Qt.AlignCenter)

        self.countdown_label = QLabel("3", alignment=Qt.AlignCenter)
        self.countdown_label.setStyleSheet("color: white; font-size: 85px; font-family: 'Jost'; font-weight: 150;")
        layout.addWidget(self.countdown_label, alignment=Qt.AlignCenter)

        fade_widget = FadeWidget(widget)

        def start_countdown_and_scan():
            self.countdown_value = 3
            self.countdown_label.setText("3")
            # Do NOT reset self.latest_emotion/self.latest_mood here!

            def update_countdown():
                if self.countdown_value > 0:
                    self.countdown_label.setText(str(self.countdown_value))
                    QTimer.singleShot(1000, decrease_counter)
                else:
                    # Just use the latest detected emotion from the continuous thread
                    QTimer.singleShot(0, lambda: self._on_scan_done(next_widget_index))

            def decrease_counter():
                self.countdown_value -= 1
                update_countdown()

            QTimer.singleShot(100, update_countdown)

        fade_widget.visibilityChanged = start_countdown_and_scan
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)
        fade_widget.auto = False
        return fade_widget

    # ... rest of your code ...
    def _on_scan_done(self, next_widget_index):
        fallback = "NO DETECTADO"
        for fw in self.fade_widgets:
            if hasattr(fw, "set_emotion"):
                fw.set_emotion(self.latest_mood if self.latest_mood else fallback)
        self.fade_to(self.current, next_widget_index)
    def create_deteced_emotion_widget(self, next_widget_index1, next_widget_index2):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Initial Voronoi label
        self.voronoi_label = QLabel()
        self.voronoi_label.setFixedSize(800, 480)
        layout.addWidget(self.voronoi_label)
        self.voronoi = VoronoiWidget(self.voronoi_label, num_points=1000, edges_per_tick=100)

        # Overlay text container (fills the Voronoi area)
        self.text_container = QWidget(self.voronoi_label)
        self.text_container.setStyleSheet("background: transparent;")
        self.text_container.setGeometry(0, 0, 800, 480)
        text_layout = QVBoxLayout(self.text_container)
        text_layout.setContentsMargins(30, 30, 30, 30)

        # --- Top bar with title and clickable labels ---
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(0)

        title_label = QLabel("ESTADO DE ÁNIMO\nDETECTADO:")
        title_label.setStyleSheet("color: white; font-size: 40px; font-family: 'Jost'; font-weight: 200; background: transparent;")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        top_bar.addWidget(title_label)
        top_bar.addStretch()


        text_layout.addLayout(top_bar)

        # Emotion label
        self.emotion_label = QLabel()
        self.emotion_label.setStyleSheet("color: white; font-size: 55px; font-family: 'Jost'; font-weight: 200; background: transparent;")
        self.emotion_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        text_layout.addWidget(self.emotion_label)
        text_layout.addStretch()
        text_layout.addStretch()

        # --- Bottom bar with clickable labels ---
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()

        guardar_label = QLabel("GUARDAR")
        guardar_label.setStyleSheet("""
            color: white;
            font-size: 25px;
            font-family: 'Jost';
            font-weight: 100;
            padding: 4px 5px;
            background: transparent;
            border-bottom: 3px solid orange;
            margin-right: 20px;
        """)
        #guardar_label.setCursor(Qt.PointingHandCursor)
        guardar_label.mousePressEvent = lambda event: self.fade_to(self.current, next_widget_index1)
        bottom_bar.addWidget(guardar_label)

        reintentar_label = QLabel("REINTENTAR")
        reintentar_label.setStyleSheet("""
            color: white;
            font-size: 25px;
            font-family: 'Jost';
            font-weight: 100;
            padding: 4px 5px;
            background: transparent;
            border-bottom: 3px solid orange;
        """)
        #reintentar_label.setCursor(Qt.PointingHandCursor)
        reintentar_label.mousePressEvent = lambda event: self.fade_to(self.current, next_widget_index2)
        bottom_bar.addWidget(reintentar_label)

        text_layout.addLayout(bottom_bar)
        # Voronoi rendering logic
        def update_voronoi():
            pixmap = QPixmap(self.voronoi_label.size())
            pixmap.fill(Qt.black)
            self.voronoi.render(pixmap)
            self.voronoi_label.setPixmap(pixmap)
        self.voronoi.update = update_voronoi

        fade_widget = FadeWidget(widget)

        def on_visibility():
            mood = self.latest_mood if self.latest_mood else "NO DETECTADO"
            self.emotion_label.setText(mood)

            voronoi_params = {
                "MUY FELIZ":   {"num_points": 50, "edges_per_tick": 10},
                "FELIZ":       {"num_points": 100, "edges_per_tick": 20},
                "NORMAL":      {"num_points": 150,  "edges_per_tick": 30},
                "TRISTE":      {"num_points": 200,  "edges_per_tick": 40},
                "MUY TRISTE":  {"num_points": 250,  "edges_per_tick": 50},
            }
            params = voronoi_params.get(mood, {"num_points": 700, "edges_per_tick": 60})

            # Remove old Voronoi label and overlay
            layout.removeWidget(self.voronoi_label)
            self.voronoi_label.deleteLater()

            # Create new Voronoi label
            self.voronoi_label = QLabel()
            self.voronoi_label.setFixedSize(800, 480)
            layout.insertWidget(0, self.voronoi_label)
            self.voronoi = VoronoiWidget(self.voronoi_label, num_points=params["num_points"], edges_per_tick=params["edges_per_tick"])

            # Re-attach overlay to new label
            self.text_container.setParent(self.voronoi_label)
            self.text_container.setGeometry(0, 0, 800, 480)

            def update_voronoi_new():
                pixmap = QPixmap(self.voronoi_label.size())
                pixmap.fill(Qt.black)
                self.voronoi.render(pixmap)
                self.voronoi_label.setPixmap(pixmap)
            self.voronoi.update = update_voronoi_new

            self.voronoi.start_animation()

            # --- PWM control depending on emotion ---
            if ON_RPI:
                pwm_values = {
                    "MUY FELIZ": 255,
                    "FELIZ": 180,
                    "NORMAL": 128,
                    "TRISTE": 64,
                    "MUY TRISTE": 30,
                }
                pi.set_PWM_dutycycle(PWM_PIN, pwm_values.get(mood, 0))

        fade_widget.visibilityChanged = on_visibility

        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        fade_widget.auto = False
        fade_widget.duration = 0

        return fade_widget
    def create_describe_emotion_widget(self, next_widget_index):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("¿CÓMO DESCRIBIRÍAS LO QUE SIENTES?")
        title.setStyleSheet("color: white; font-size: 40px; font-family: 'Jost'; font-weight: 200;")
        title.setAlignment(Qt.AlignLeft)
        layout.addWidget(title)
        layout.addSpacing(10)

        # Emotions grid as buttons 
        emotions = [
            ["EUFORÍA", "MONOTONÍA", "NOSTALGIA"],
            ["AGRADECIMIENTO", "DECEPCIÓN", "APATÍA"],
            ["ENTUSIASMO", "SOLEDAD", "EMOCIÓN"],
            ["ORGULLO", "VACÍO", "MELANCOLÍA"],
            ["SATISFACCIÓN", "ESPERANZA", "DESANIMO"],
            ["TRANQUILIDAD", "DOLOR", "ABURRIMIENTO"],
            ["MOTIVACIÓN", "INCOMPRENSIÓN", ""]
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(10, 5, 10, 5)

        self.selected_emotion = set()
        self.emotion_buttons = []

        def on_emotion_clicked(word, btn):
            # Deselect all
            if word in self.selected_emotion:
                self.selected_emotion.remove(word)
                btn.setStyleSheet("color: white; font-size: 20px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
            else:
                self.selected_emotion.add(word)
                btn.setStyleSheet("color: orange; font-size: 20px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")

        for row, row_words in enumerate(emotions):
            for col, word in enumerate(row_words):
                if word:
                    btn = QPushButton(word)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setStyleSheet("color: white; font-size: 20px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
                    btn.clicked.connect(lambda checked, w=word, b=btn: on_emotion_clicked(w, b))
                    grid.addWidget(btn, row, col)
                    self.emotion_buttons.append(btn)

        layout.addLayout(grid)
        layout.addStretch()

        # Siguiente button in bottom right
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        siguiente_btn = QPushButton("SIGUIENTE")
        siguiente_btn.setStyleSheet("""
            background-color: #000;
            color: white;
            font-size: 25px;
            font-family: 'Jost';
            font-weight: 100;
            border: none;
        """)
        button_container = QVBoxLayout()
        button_container.setSpacing(0)
        button_container.setContentsMargins(0, 0, 0, 0)
        button_container.addWidget(siguiente_btn)
        underline = QFrame()
        underline.setFrameShape(QFrame.HLine)
        underline.setFrameShadow(QFrame.Plain)
        underline.setStyleSheet("background-color: orange;")
        underline.setFixedHeight(2)
        button_container.addWidget(underline)
        button_layout.addLayout(button_container)
        layout.addLayout(button_layout)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        def on_next():
            print("Selected emotion:", self.selected_emotion)  # You can use this value elsewhere
            self.fade_to(self.current, next_widget_index)

        siguiente_btn.clicked.connect(on_next)

        siguiente_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index))
        def reset_emotion_selection():
            self.selected_emotion.clear()
            for btn in self.emotion_buttons:
                btn.setStyleSheet("color: white; font-size: 20px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
        fade_widget.visibilityChanged = reset_emotion_selection
    
    def create_cause_emotion_widget(self, next_widget_index):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("¿CUÁLES SON LOS MOTIVOS?")
        title.setStyleSheet("color: white; font-size: 40px; font-family: 'Jost'; font-weight: 200;")
        title.setAlignment(Qt.AlignLeft)
        layout.addWidget(title)
        layout.addSpacing(20)

        # Motives grid as toggle buttons
        motives = [
            ["FAMILIA", "AMOR", "TRABAJO"],
            ["AMIGOS", "LOGROS", "RECUERDOS"],
            ["NOTICIAS", "ESTUDIOS", "PÉRDIDA"],
            ["FIESTA", "COMIDA", ""]
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(10, 5, 10, 5)

        self.selected_motives = set()
        self.motive_buttons = []

        def on_motive_clicked(word, btn):
            if word in self.selected_motives:
                self.selected_motives.remove(word)
                btn.setStyleSheet("color: white; font-size: 20px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
            else:
                self.selected_motives.add(word)
                btn.setStyleSheet("color: orange; font-size: 20px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")

        for row, row_words in enumerate(motives):
            for col, word in enumerate(row_words):
                if word:
                    btn = QPushButton(word)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setStyleSheet("color: white; font-size: 20px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
                    btn.setCheckable(True)
                    btn.clicked.connect(lambda checked, w=word, b=btn: on_motive_clicked(w, b))
                    grid.addWidget(btn, row, col)
                    self.motive_buttons.append(btn)

        layout.addLayout(grid)
        layout.addStretch()

        # GUARDAR button in bottom right
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        guardar_btn = QPushButton("GUARDAR")
        guardar_btn.setStyleSheet("""
            background-color: #000;
            color: white;
            font-size: 25px;
            font-family: 'Jost';
            font-weight: 100;
            border: none;
        """)
        button_container = QVBoxLayout()
        button_container.setSpacing(0)
        button_container.setContentsMargins(0, 0, 0, 0)
        button_container.addWidget(guardar_btn)
        underline = QFrame()
        underline.setFrameShape(QFrame.HLine)
        underline.setFrameShadow(QFrame.Plain)
        underline.setStyleSheet("background-color: orange;")
        underline.setFixedHeight(2)
        button_container.addWidget(underline)
        button_layout.addLayout(button_container)
        layout.addLayout(button_layout)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        def on_save():
            print("Selected motives:", list(self.selected_motives))  # Use this list as needed
            self.fade_to(self.current, next_widget_index)

        guardar_btn.clicked.connect(on_save)
        def reset_motive_selection():
            self.selected_motives.clear()
            for btn in self.motive_buttons:  
                btn.setChecked(False)
                btn.setStyleSheet("color: white; font-size: 20px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
        fade_widget.visibilityChanged = reset_motive_selection
    def create_send_to_contacts_widget(self, next_widget_index_si, next_widget_index_no):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("¿TE GUSTARÍA\nCOMPARTIRLO CON\nTUS CONTACTOS?")
        title.setStyleSheet("color: white; font-size: 50px; font-family: 'Jost'; font-weight: 200;")
        title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(title)
        layout.addStretch()

        # SI / NO buttons with underline
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setContentsMargins(10, 0, 0, 10)

        # SI button with underline
        si_container = QVBoxLayout()
        si_container.setSpacing(0)
        si_container.setContentsMargins(10, 0, 10, 0)
        si_btn = QPushButton("SI")
        si_btn.setCursor(Qt.PointingHandCursor)
        si_btn.setStyleSheet("color: white; font-size: 25px; font-family: 'Jost'; border: none; background: transparent;")
        si_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index_si))
        si_container.addWidget(si_btn)
        si_underline = QFrame()
        si_underline.setFrameShape(QFrame.HLine)
        si_underline.setFrameShadow(QFrame.Plain)
        si_underline.setStyleSheet("background-color: orange;")
        si_underline.setFixedHeight(2)
        si_container.addWidget(si_underline)

        # NO button with underline
        no_container = QVBoxLayout()
        no_container.setSpacing(0)
        no_container.setContentsMargins(10, 0, 10, 0)
        no_btn = QPushButton("NO")
        no_btn.setCursor(Qt.PointingHandCursor)
        no_btn.setStyleSheet("color: white; font-size: 25px; font-family: 'Jost'; border: none; background: transparent;")
        no_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index_no))
        no_container.addWidget(no_btn)
        no_underline = QFrame()
        no_underline.setFrameShape(QFrame.HLine)
        no_underline.setFrameShadow(QFrame.Plain)
        no_underline.setStyleSheet("background-color: orange;")
        no_underline.setFixedHeight(2)
        no_container.addWidget(no_underline)

        button_layout.addLayout(si_container)
        button_layout.addSpacing(10)
        button_layout.addLayout(no_container)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)


    def create_statistics_widget(self, next_widget_index):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Top bar with title and cross ---
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(0)

        title = QLabel()
        title.setStyleSheet("color: white; margin-left: 10px; font-size: 28px; font-family: 'Jost';")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        top_bar.addWidget(title)
        top_bar.addStretch()

        cross_btn = QPushButton("✕")
        cross_btn.setFixedSize(48, 48)
        cross_btn.setStyleSheet("""
            QPushButton {
                color: white;
                font-size: 36px;
                font-family: 'Jost';
                background: transparent;
                border: none;
                margin-right:30px;
                margin-top: 0px;
            }
            QPushButton:hover {
                color: orange;
            }
        """)
        top_bar.addWidget(cross_btn)

        layout.addLayout(top_bar)
        layout.addSpacing(10)

        chart = StatisticsChart(title_label=title, start_date=date(2024, 4, 1))
        layout.addWidget(chart)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        cross_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index))

        # Example day data for demo
        def get_day_data(day_idx):
            # Replace with your real data lookup

            return {
                "date": "19 / 04 / 2025",
                "entries": [
                    {"time": "10:45", "mood": "BIEN", "emociones": ["TRANQUILIDAD"], "motivos": ["FIESTA"]},
                    {"time": "12:00", "mood": "NORMAL", "emociones": ["APATÍA"], "motivos": ["TRABAJO"]},
                ]
            }

        def show_day_details(day_idx):
            day_data = get_day_data(day_idx)
            details_widget = self.create_day_details_widget(day_data, next_widget_index=self.fade_widgets.index(fade_widget))
            self.fade_to(self.current, self.fade_widgets.index(details_widget))

        chart.day_clicked.connect(show_day_details)
    def create_day_details_widget(self, day_data, next_widget_index):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Fullscreen image (replace 'info_dia.png' with your image file)
        image_label = QLabel()
        image_label.setPixmap(QPixmap("info_dia.png").scaled(800, 440, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(image_label)

        # Cross button (top-right, overlay style)
        cross_btn = QPushButton("✕", widget)
        cross_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background: rgba(0,0,0,0.5);
                border: none;
                font-size: 36px;
                font-family: 'Jost';
                font-weight: 200;
                padding: 0 12px;
            }
            QPushButton:hover {
                color: orange;
            }
        """)
        cross_btn.setFixedSize(40, 40)
        cross_btn.move(740, 10)  # Position at top-right (800-48-12, 10)
        cross_btn.raise_()
        cross_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index))

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)
        return fade_widget
    
    def _start_auto_timer_for_current(self):
        current_widget = self.fade_widgets[self.current]
        if getattr(current_widget, "auto", False):
            self.timer.start(getattr(current_widget, "duration", 0))
        else:
            self.timer.stop()

    def _auto_switch(self):
        # Called by timer: switch to the next widget
        next_idx = self.fade_widgets[self.current].next_widget_index
        self.fade_to(self.current, next_idx)

    def fade_to(self, from_idx, to_idx):
        fade_out_widget = self.fade_widgets[from_idx]
        fade_in_widget = self.fade_widgets[to_idx]

        fade_out_anim = QPropertyAnimation(fade_out_widget, b"opacity")
        fade_out_anim.setDuration(400)
        fade_out_anim.setStartValue(1)
        fade_out_anim.setEndValue(0)
        fade_out_anim.setEasingCurve(QEasingCurve.InOutQuad)

        def on_fade_out_finished():
            self.stack.setCurrentWidget(fade_in_widget)
            fade_in_widget.set_opacity(0)
            if hasattr(fade_in_widget, 'visibilityChanged'):
                fade_in_widget.visibilityChanged()
            fade_in_anim = QPropertyAnimation(fade_in_widget, b"opacity")
            fade_in_anim.setDuration(400)
            fade_in_anim.setStartValue(0)
            fade_in_anim.setEndValue(1)
            fade_in_anim.setEasingCurve(QEasingCurve.InOutQuad)
            fade_in_anim.start()
            self._animations.append(fade_in_anim)
            fade_in_anim.finished.connect(lambda: self._animations.remove(fade_in_anim))
            # After fade in, update current and setup timer for new widget
            self.current = to_idx
            self._start_auto_timer_for_current()


        fade_out_anim.finished.connect(on_fade_out_finished)
        fade_out_anim.start()
        self._animations.append(fade_out_anim)
        fade_out_widget.set_opacity(1)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("QWidget { background-color: #000000; }")
    font_path = os.path.join(os.path.dirname(__file__), "Jost-Light.ttf")
    font_id = QFontDatabase.addApplicationFont(font_path)
    jostLight = QFontDatabase.applicationFontFamilies(font_id)[0]

    window = MainScreen()
    window.show()

    # --- Move to second display if available ---
    screens = app.screens()
    if len(screens) > 1:
        second_screen = screens[1]
        geometry = second_screen.geometry()
        # Move and resize the window to fill the second screen
        window.move(geometry.left(), geometry.top())
        window.resize(800, 480)
    else:
        print("Only one display detected. Showing on primary display.")

    sys.exit(app.exec_())