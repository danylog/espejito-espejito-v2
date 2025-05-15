import sys
import os
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


class StatisticsChart(QWidget):
    day_clicked = pyqtSignal(int)  # index in self.data
    def __init__(self, parent=None, start_date=None, title_label=None):
        super().__init__(parent)
        self.setMinimumSize(1200, 650)
        self.setStyleSheet("background: transparent;")
        self.data = [2, 3, 4, 2, 4, 1, 2, 3, 2, 1, 3, 4, 2, 2, 3, 1, 2, 4, 3, 2, 1, 2, 3, 4, 2, 1, 3, 2]
        self.window_size = 7
        self.window_start = 0
        self.num_windows = (len(self.data) + self.window_size - 1) // self.window_size
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
        left = 120
        right = 40
        top = 60
        bottom = 130

        # Draw horizontal grid lines and labels
        levels = ["MUY BIEN", "BIEN", "NORMAL", "MAL", "MUY MAL"]
        for i, label in enumerate(levels):
            y = top + i * (h - top - bottom) / 4
            painter.setPen(grid_pen)
            painter.drawLine(left, int(y), w - right, int(y))
            painter.setPen(QColor(180, 180, 180) if i in [0, 4] else QColor(255, 255, 255))
            painter.setFont(QFont("Jost", 24))
            painter.drawText(20, int(y) + 10, label)

        # Draw line and dots for visible window
        points = []
        visible_data = self.data[self.window_start:self.window_start + self.window_size]
        for i, value in enumerate(visible_data):
            x = left + i * (w - left - right) / (self.window_size - 1)
            y = top + (4 - value) * (h - top - bottom) / 4
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
        painter.setFont(QFont("Jost", 32))
        for i, day in enumerate(days):
            x = left + i * (w - left - right) / (self.window_size - 1)
            painter.drawText(int(x) - 16, h - 100, 32, 40, Qt.AlignCenter, day)

        # Draw navigation dots (and store clickable areas)
        self.dot_rects = []
        dot_y = h - 50
        dot_x0 = w // 2 - (self.num_windows * 15)
        for i in range(self.num_windows):
            rect = QRect(dot_x0 + i * 30, dot_y, 16, 16)
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
            if abs(event.x() - x) < 30:  # 30px tolerance
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
    def __init__(self, parent=None):
        self.r = 217
        self.g = 134
        self.b = 86
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000;")
        self.setFixedSize(1920, 800)
        
        # Initialize data structures
        self.points = []
        self.shown_edges = set()
        self.all_edges = []
        self.edge_graph = {}
        self.edge_lookup = {}  # Added edge_lookup dictionary
        self.visited_vertices = set()
        self.edges_to_add = []  # Added edges_to_add list
        self.vor = None
        self.edges_per_tick = 500
        
        # Generate random points
        num_points = 10000
        margin = 0
        width = self.width()
        height = self.height()
        
        # Generate points using numpy
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
        edge_pen.setWidth(1)
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
        self.setGeometry(100, 100, 1920, 1080)

        self.current = 0  # Start with the first widget

        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #000000;")
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

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
        self.create_widget2(next_widget_index1=3, next_widget_index2=9) #2
        self.create_show_face_widget(next_widget_index=4)            #3
        self.create_scan_face_countdown_widget(next_widget_index=5)     #4
        self.create_deteced_emotion_widget(next_widget_index1=6, next_widget_index2=4)      #5
        self.create_describe_emotion_widget(next_widget_index=7) #6
        self.create_cause_emotion_widget(next_widget_index=8) #7
        self.create_send_to_contacts_widget(next_widget_index_no=0, next_widget_index_si=0) #8
        self.create_statistics_widget(next_widget_index=2) #9
       # self.create_day_details_widget(next_widget_index=9) #10
        


        # Set the first widget as visible
        self.stack.setCurrentWidget(self.fade_widgets[0])
        self.fade_widgets[0].set_opacity(1)

        # Start the timer if the first widget has auto transition
        self._start_auto_timer_for_current()

    def create_initial_widget(self, next_widget_index):
        """
        Creates the initial widget with an image and auto transition to widget1.
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)

        # Add an image to the initial widget
        label = QLabel()
        label.setPixmap(QPixmap("cupra.png").scaled(400, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
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
        """
        Creates the first widget with manual transition via button.
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
          # Left, Top, Right, Bottom margins

        label = QLabel("LO QUE SIENTES\nIMPORTA", alignment=Qt.AlignCenter)

        label.setStyleSheet(f"color: white; font-size: 150px; font-family: '{jostLight}';")
        layout.addWidget(label)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        # Connect button for manual transition
        # Store transition behavior
        fade_widget.auto = True
        fade_widget.duration = 2000  # Auto transition after 3 seconds
        fade_widget.next_widget_index = next_widget_index

    def create_widget2(self, next_widget_index1, next_widget_index2):
        """
        Creates the second widget with auto transition after 2000ms.
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(108, 108, 50, 20)
        label1 = QLabel("ENTENDER TU ESTADO DE ÁNIMO\nES CLAVE PARA PODER REFLEXIONAR SOBRE\nLO QUE PODRÍA INFLUIR EN TU\nBIENESTAR EMOCIONAL.", alignment=Qt.AlignLeft)
        font_path1 = os.path.join(os.path.dirname(__file__), "Jost-ExtraLight.ttf")
        font_id1 = QFontDatabase.addApplicationFont(font_path1)
        if font_id1 == -1:
            print("Failed to load font: Jost-ExtraLight.ttf")
        else:
            jostExtraLight = QFontDatabase.applicationFontFamilies(font_id1)[0]
            print("Loaded font family:", jostExtraLight)

        label1.setStyleSheet(f"color: white; font-size: 75px; font-family: 'Jost'; font-weight: 200;")
        layout.addWidget(label1)

        button = QPushButton("ESCANEAR ESTADO EMOCIONAL")
        button.setStyleSheet("background-color: #000; color: white; font-size: 50px; font-family: 'Jost'; font-weight: 150; border-bottom: 40px solid white;")
        layout.addWidget(button, alignment=Qt.AlignLeft)
                
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet("background-color: orange;")
        line.setFixedSize(750, 5)
        layout.addWidget(line)

        button2 = QPushButton("VER ESTADÍSTICAS DEL ESTADO EMOCIONAL")
        button2.setStyleSheet("background-color: #000; color: white; font-size: 50px; font-family: 'Jost'; font-weight: 150;")
        layout.addWidget(button2, alignment=Qt.AlignLeft)

        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Plain)
        line2.setStyleSheet("background-color: orange;")
        line2.setFixedSize(1000, 5)
        layout.addWidget(line2)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        # Connect button for manual transition
        button.clicked.connect(lambda: self.fade_to(self.current, next_widget_index1))
        button2.clicked.connect(lambda: self.fade_to(self.current, next_widget_index2))


        # Store transition behavior
        fade_widget.auto = False
    
    def create_show_face_widget(self, next_widget_index):
        """
        Creates the widget that shows the face with a button to go back.
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)

        label = QLabel("MUESTRA CON TU\nROSTRO CÓMO TE\nSIENTES", alignment=Qt.AlignCenter)
        label.setStyleSheet("color: white; font-size: 150px; font-family: 'Jost'; font-weight: 200;")
        layout.addWidget(label, alignment=Qt.AlignCenter)


        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        # Connect button for manual transition
        fade_widget.auto = True
        fade_widget.duration = 4000  # Auto transition after 3 seconds
        fade_widget.next_widget_index = next_widget_index

    def create_scan_face_countdown_widget(self, next_widget_index):
        """
        Creates the countdown widget with a button to go back.
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)

        # Add a label for the title
        label = QLabel("ESCANEANDO\nEMOCIONES", alignment=Qt.AlignCenter)
        label.setStyleSheet("color: white; font-size: 150px; font-family: 'Jost'; font-weight: 200;")
        layout.addWidget(label, alignment=Qt.AlignCenter)

        # Add a label for the countdown
        self.countdown_label = QLabel("3", alignment=Qt.AlignCenter)
        self.countdown_label.setStyleSheet("color: white; font-size: 200px; font-family: 'Jost'; font-weight: 150;")
        layout.addWidget(self.countdown_label, alignment=Qt.AlignCenter)

        fade_widget = FadeWidget(widget)

        # Create a method to start countdown when this widget becomes visible
        def start_countdown():
            self.countdown_value = 3  # Reset countdown
            self.countdown_label.setText("3")  # Reset label

            def update_countdown():
                print(f"Current countdown value: {self.countdown_value}")
                if self.countdown_value > 0:
                    self.countdown_label.setText(str(self.countdown_value))
                    QTimer.singleShot(1000, decrease_counter)
                else:
                    self.fade_to(self.current, next_widget_index)

            def decrease_counter():
                self.countdown_value -= 1
                update_countdown()

            # Start the countdown
            QTimer.singleShot(100, update_countdown)

        # Connect the countdown start to when this widget becomes visible
        fade_widget.visibilityChanged = start_countdown
        
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)
        fade_widget.auto = False


        return fade_widget

    def create_deteced_emotion_widget(self, next_widget_index1, next_widget_index2):
        # Create main widget
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")

        # ... previous code ...
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        voronoi_label = QLabel()
        voronoi_label.setFixedSize(1800, 800)
        layout.addWidget(voronoi_label)

        voronoi = VoronoiWidget()

        # --- Overlay text container ---
        text_container = QWidget(voronoi_label)
        # text_container.setAttribute(Qt.WA_TransparentForMouseEvents)
        text_container.setStyleSheet("background: transparent;")
        text_container.setGeometry(0, 0, 1600, 800)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(100, 20, 0, 0)  # Adjust as needed

        # Title label
        title_label = QLabel("ESTADO DE ÁNIMO\nDETECTADO:")
        title_label.setStyleSheet("color: white; font-size: 150px; font-family: 'Jost'; font-weight: 200; background: transparent;")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        text_layout.addWidget(title_label)

        # Dynamic emotion label
        self.emotion_label = QLabel("FELIZ")  # Default text
        self.emotion_label.setStyleSheet("color: white; font-size: 75px; font-family: 'Jost'; font-weight: 200; background: transparent;")
        self.emotion_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        text_layout.addWidget(self.emotion_label)
        text_layout.addStretch()

        
        self.saveButton = QPushButton("GUARDAR")
        self.saveButton.setStyleSheet("background-color: #000; color: white; margin-left: 100px; font-size: 50px; font-family: 'Jost'; font-weight: 100;")
        self.tryButton = QPushButton("REINTENTAR")
        self.tryButton.setStyleSheet("background-color: #000; color: white; font-size: 50px; font-family: 'Jost'; font-weight: 100;")
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.tryButton)
        # --- GUARDAR button with underline ---
        guardar_container = QVBoxLayout()
        guardar_container.setSpacing(0)
        guardar_container.setContentsMargins(0, 0, 0, 0)
        guardar_container.addWidget(self.saveButton)
        guardar_underline = QFrame()
        guardar_underline.setFrameShape(QFrame.HLine)
        guardar_underline.setFrameShadow(QFrame.Plain)
        guardar_underline.setStyleSheet("background-color: orange; margin-left: 100px;")
        guardar_underline.setFixedHeight(6)
        guardar_container.addWidget(guardar_underline)

        # --- REINTENTAR button with underline ---
        reintentar_container = QVBoxLayout()
        reintentar_container.setSpacing(0)
        reintentar_container.setContentsMargins(0, 0, 0, 0)
        reintentar_container.addWidget(self.tryButton)
        reintentar_underline = QFrame()
        reintentar_underline.setFrameShape(QFrame.HLine)
        reintentar_underline.setFrameShadow(QFrame.Plain)
        reintentar_underline.setStyleSheet("background-color: orange;")
        reintentar_underline.setFixedHeight(6)
        reintentar_container.addWidget(reintentar_underline)

        # --- Horizontal layout for both buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addLayout(reintentar_container)
        button_layout.addSpacing(40)  # Space between buttons
        button_layout.addLayout(guardar_container)
        text_layout.addLayout(button_layout)

        # --- Voronoi rendering logic ---
        def update_voronoi():
            pixmap = QPixmap(voronoi_label.size())
            pixmap.fill(Qt.black)
            voronoi.render(pixmap)
            voronoi_label.setPixmap(pixmap)

        voronoi.update = update_voronoi

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        def start_animation():
            print("Starting Voronoi animation")
            voronoi.start_animation()

        fade_widget.visibilityChanged = start_animation

        # Allow dynamic update from outside
        fade_widget.set_emotion = self.emotion_label.setText

        fade_widget.auto = False
        fade_widget.duration = 0
        self.saveButton.clicked.connect(lambda: self.fade_to(self.current, next_widget_index1))
        self.tryButton.clicked.connect(lambda: self.fade_to(self.current, next_widget_index2))

        return fade_widget

    def create_describe_emotion_widget(self, next_widget_index):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("¿CÓMO DESCRIBIRÍAS\nLO QUE SIENTES?")
        title.setStyleSheet("color: white; font-size: 70px; margin-left: 100px;  font-family: 'Jost'; font-weight: 200;")
        title.setAlignment(Qt.AlignLeft)
        layout.addWidget(title)
        layout.addSpacing(20)

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
        grid.setHorizontalSpacing(40)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(20, 10, 20, 10)

        self.selected_emotion = set()
        self.emotion_buttons = []

        def on_emotion_clicked(word, btn):
            # Deselect all
            if word in self.selected_emotion:
                self.selected_emotion.remove(word)
                btn.setStyleSheet("color: white; font-size: 30px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
            else:
                self.selected_emotion.add(word)
                btn.setStyleSheet("color: orange; font-size: 30px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none; text-decoration: underline;")

        for row, row_words in enumerate(emotions):
            for col, word in enumerate(row_words):
                if word:
                    btn = QPushButton(word)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setStyleSheet("color: white; font-size: 30px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
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
            font-size: 28px;
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
        underline.setFixedHeight(3)
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
    
    def create_cause_emotion_widget(self, next_widget_index):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("¿CUÁLES SON LOS\nMOTIVOS?")
        title.setStyleSheet("color: white; font-size: 90px; margin-left: 100px; font-family: 'Jost'; font-weight: 200;")
        title.setAlignment(Qt.AlignLeft)
        layout.addWidget(title)
        layout.addSpacing(40)

        # Motives grid as toggle buttons
        motives = [
            ["FAMILIA", "AMOR", "TRABAJO"],
            ["AMIGOS", "LOGROS", "RECUERDOS"],
            ["NOTICIAS", "ESTUDIOS", "PÉRDIDA"],
            ["FIESTA", "COMIDA", ""]
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(60)
        grid.setVerticalSpacing(20)
        grid.setContentsMargins(60, 20, 60, 20)

        self.selected_motives = set()
        self.motive_buttons = []

        def on_motive_clicked(word, btn):
            if word in self.selected_motives:
                self.selected_motives.remove(word)
                btn.setStyleSheet("color: white; font-size: 38px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
            else:
                self.selected_motives.add(word)
                btn.setStyleSheet("color: orange; font-size: 38px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none; text-decoration: underline;")

        for row, row_words in enumerate(motives):
            for col, word in enumerate(row_words):
                if word:
                    btn = QPushButton(word)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setStyleSheet("color: white; font-size: 38px; font-family: 'Jost'; font-weight: 200; background: transparent; border: none;")
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
            font-size: 32px;
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
        underline.setFixedHeight(3)
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
    def create_send_to_contacts_widget(self, next_widget_index_si, next_widget_index_no):
        widget = QWidget()
        widget.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(40, 40, 40, 40)

        # Title
        title = QLabel("¿TE GUSTARÍA\nCOMPARTIRLO CON\nTUS CONTACTOS?")
        title.setStyleSheet("color: white; font-size: 100px; font-family: 'Jost'; font-weight: 200;")
        title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(title)
        layout.addStretch()

        # SI / NO buttons with underline
        button_layout = QHBoxLayout()
        button_layout.setSpacing(60)
        button_layout.setContentsMargins(40, 0, 0, 40)

        # SI button with underline
        si_container = QVBoxLayout()
        si_container.setSpacing(0)
        si_container.setContentsMargins(0, 0, 0, 0)
        si_btn = QPushButton("SI")
        si_btn.setCursor(Qt.PointingHandCursor)
        si_btn.setStyleSheet("color: white; font-size: 38px; font-family: 'Jost'; border: none; background: transparent;")
        si_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index_si))
        si_container.addWidget(si_btn)
        si_underline = QFrame()
        si_underline.setFrameShape(QFrame.HLine)
        si_underline.setFrameShadow(QFrame.Plain)
        si_underline.setStyleSheet("background-color: orange;")
        si_underline.setFixedHeight(3)
        si_container.addWidget(si_underline)

        # NO button with underline
        no_container = QVBoxLayout()
        no_container.setSpacing(0)
        no_container.setContentsMargins(0, 0, 0, 0)
        no_btn = QPushButton("NO")
        no_btn.setCursor(Qt.PointingHandCursor)
        no_btn.setStyleSheet("color: white; font-size: 38px; font-family: 'Jost'; border: none; background: transparent;")
        no_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index_no))
        no_container.addWidget(no_btn)
        no_underline = QFrame()
        no_underline.setFrameShape(QFrame.HLine)
        no_underline.setFrameShadow(QFrame.Plain)
        no_underline.setStyleSheet("background-color: orange;")
        no_underline.setFixedHeight(3)
        no_container.addWidget(no_underline)

        button_layout.addLayout(si_container)
        button_layout.addSpacing(40)
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

        title = QLabel()
        title.setStyleSheet("color: white; font-size: 48px; font-family: 'Jost';")
        title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(title)
        layout.addSpacing(10)

        chart = StatisticsChart(title_label=title, start_date=date(2024, 4, 1))
        layout.addWidget(chart)

        # Cross button at top right
        cross_btn = QPushButton("✕")
        cross_btn.setFixedSize(80, 80)
        cross_btn.setStyleSheet("""
            QPushButton {
                color: white;
                font-size: 48px;
                font-family: 'Jost';
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                color: orange;
            }
        """)
        cross_layout = QHBoxLayout()
        cross_layout.addStretch()
        cross_layout.addWidget(cross_btn)
        layout.insertLayout(0, cross_layout)

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
        layout.setContentsMargins(80, 80, 80, 80)

        # Date at top
        date_label = QLabel(day_data["date"])
        date_label.setStyleSheet("color: #888; font-size: 48px; font-family: 'Jost'; font-weight: 200;")
        layout.addWidget(date_label)
        layout.addSpacing(30)

        for entry in day_data["entries"]:
            # Time and mood
            time_label = QLabel(f"{entry['time']} {entry['mood']}")
            time_label.setStyleSheet("color: white; font-size: 38px; font-family: 'Jost'; font-weight: 200;")
            layout.addWidget(time_label)
            # Divider
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setStyleSheet("background-color: #222;")
            divider.setFixedHeight(2)
            layout.addWidget(divider)
            # Emociones
            emociones_label = QLabel(f"EMOCIONES: <span style='color:#888'>{' - '.join(entry['emociones'])}</span>")
            emociones_label.setStyleSheet("color: white; font-size: 32px; font-family: 'Jost'; font-weight: 200;")
            emociones_label.setTextFormat(Qt.RichText)
            layout.addWidget(emociones_label)
            # Motivos
            motivos_label = QLabel(f"MOTIVOS: <span style='color:#888'>{' - '.join(entry['motivos'])}</span>")
            motivos_label.setStyleSheet("color: white; font-size: 32px; font-family: 'Jost'; font-weight: 200;")
            motivos_label.setTextFormat(Qt.RichText)
            layout.addWidget(motivos_label)
            layout.addSpacing(40)

        layout.addStretch()

        # Cross button at top right
        cross_btn = QPushButton("✕")
        cross_btn.setFixedSize(80, 80)
        cross_btn.setStyleSheet("""
            QPushButton {
                color: white;
                font-size: 48px;
                font-family: 'Jost';
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                color: orange;
            }
        """)
        cross_layout = QHBoxLayout()
        cross_layout.addStretch()
        cross_layout.addWidget(cross_btn)
        layout.insertLayout(0, cross_layout)

        fade_widget = FadeWidget(widget)
        self.stack.addWidget(fade_widget)
        self.fade_widgets.append(fade_widget)

        cross_btn.clicked.connect(lambda: self.fade_to(self.current, next_widget_index))
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
    sys.exit(app.exec_())