"""
WS2812B 16x16 Matrix Controller for ESP32-S3
- Visual grid editor with color picker
- Real-time serial control via PySerial
- Arduino code generation
"""
import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox
import serial
import serial.tools.list_ports
import threading
import time

ROWS, COLS = 16, 16
CELL = 32

class MatrixController:
    def __init__(self, root):
        self.root = root
        self.root.title("WS2812B 16x16 Matrix Controller")
        self.root.configure(bg="#1a1a2e")
        self.root.resizable(False, False)

        self.grid_colors = [[(0,0,0) for _ in range(COLS)] for _ in range(ROWS)]
        self.current_color = (255, 0, 0)
        self.serial_conn = None
        self.drawing = False
        self.erasing = False
        self.brightness = 50
        self.zigzag = tk.BooleanVar(value=False)

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", background="#16213e", foreground="white",
                        borderwidth=0, focuscolor="none", padding=6)
        style.map("TButton", background=[("active","#0f3460")])
        style.configure("TLabel", background="#1a1a2e", foreground="#e0e0e0")
        style.configure("TFrame", background="#1a1a2e")
        style.configure("TLabelframe", background="#1a1a2e", foreground="#e94560")
        style.configure("TLabelframe.Label", background="#1a1a2e", foreground="#e94560")
        style.configure("TScale", background="#1a1a2e", troughcolor="#16213e")

        main = ttk.Frame(self.root)
        main.pack(padx=10, pady=10)

        # Left: canvas
        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, padx=(0,10))

        ttk.Label(left, text="LED Matrix 16×16", font=("Segoe UI",14,"bold"),
                  foreground="#e94560").pack(pady=(0,5))

        canvas_frame = tk.Frame(left, bg="#0f3460", bd=2, relief=tk.RIDGE)
        canvas_frame.pack()
        self.canvas = tk.Canvas(canvas_frame, width=COLS*CELL, height=ROWS*CELL,
                                bg="#0a0a0a", highlightthickness=0)
        self.canvas.pack(padx=2, pady=2)
        self.rects = [[None]*COLS for _ in range(ROWS)]
        for r in range(ROWS):
            for c in range(COLS):
                x, y = c*CELL, r*CELL
                self.rects[r][c] = self.canvas.create_rectangle(
                    x+1, y+1, x+CELL-1, y+CELL-1, fill="#000000", outline="#1a1a2e", width=1)

        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_release)

        # Right panel
        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.Y)

        # --- Connection ---
        conn_frame = ttk.LabelFrame(right, text="Подключение", padding=8)
        conn_frame.pack(fill=tk.X, pady=(0,8))

        self.port_var = tk.StringVar()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var,
                                       values=ports, width=14, state="readonly")
        self.port_combo.pack(pady=2)
        if ports:
            self.port_combo.current(0)

        btn_row = ttk.Frame(conn_frame)
        btn_row.pack(pady=4)
        self.connect_btn = ttk.Button(btn_row, text="Подключить", command=self._toggle_connect)
        self.connect_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="🔄", width=3, command=self._refresh_ports).pack(side=tk.LEFT)

        self.status_label = ttk.Label(conn_frame, text="● Отключено", foreground="#ff4444",
                                      font=("Segoe UI",9))
        self.status_label.pack()

        zigzag_cb = ttk.Checkbutton(conn_frame, text="Змейка (zigzag)",
                                     variable=self.zigzag)
        zigzag_cb.pack(pady=(4,0))

        # --- Color ---
        color_frame = ttk.LabelFrame(right, text="Цвет", padding=8)
        color_frame.pack(fill=tk.X, pady=(0,8))

        self.color_preview = tk.Canvas(color_frame, width=140, height=40,
                                       bg="#ff0000", highlightthickness=1,
                                       highlightbackground="#333", cursor="hand2")
        self.color_preview.pack(pady=4)
        self.color_preview.bind("<Button-1>", lambda e: self._pick_color())

        ttk.Label(color_frame, text="Нажмите для выбора цвета",
                  font=("Segoe UI",8)).pack()

        # Preset colors
        presets_frame = ttk.Frame(color_frame)
        presets_frame.pack(pady=6)
        preset_colors = [
            "#FF0000","#00FF00","#0000FF","#FFFF00",
            "#FF00FF","#00FFFF","#FF8000","#FFFFFF",
            "#FF1493","#7B68EE","#00FA9A","#FFD700"
        ]
        for i, pc in enumerate(preset_colors):
            btn = tk.Canvas(presets_frame, width=28, height=28, bg=pc,
                           highlightthickness=1, highlightbackground="#333", cursor="hand2")
            btn.grid(row=i//4, column=i%4, padx=2, pady=2)
            btn.bind("<Button-1>", lambda e, c=pc: self._set_color_hex(c))

        # --- Brightness ---
        br_frame = ttk.LabelFrame(right, text="Яркость", padding=8)
        br_frame.pack(fill=tk.X, pady=(0,8))

        self.br_var = tk.IntVar(value=50)
        self.br_scale = ttk.Scale(br_frame, from_=1, to=255, variable=self.br_var,
                                  orient=tk.HORIZONTAL, command=self._on_brightness)
        self.br_scale.pack(fill=tk.X)
        self.br_label = ttk.Label(br_frame, text="50")
        self.br_label.pack()

        # --- Actions ---
        act_frame = ttk.LabelFrame(right, text="Действия", padding=8)
        act_frame.pack(fill=tk.X, pady=(0,8))

        ttk.Button(act_frame, text="🗑 Очистить матрицу", command=self._clear_all).pack(fill=tk.X, pady=2)
        ttk.Button(act_frame, text="📤 Отправить всё на ESP", command=self._send_all).pack(fill=tk.X, pady=2)
        ttk.Button(act_frame, text="🎨 Залить цветом", command=self._fill_all).pack(fill=tk.X, pady=2)

        # --- Export ---
        exp_frame = ttk.LabelFrame(right, text="Экспорт", padding=8)
        exp_frame.pack(fill=tk.X)

        ttk.Button(exp_frame, text="💾 Сгенерировать Arduino код", command=self._export_code).pack(fill=tk.X, pady=2)

        # --- Info ---
        ttk.Label(right, text="ЛКМ — рисовать\nПКМ — стирать",
                  font=("Segoe UI",8), foreground="#888").pack(pady=(8,0))

    # --- Color ---
    def _pick_color(self):
        c = colorchooser.askcolor(initialcolor=self._rgb_to_hex(self.current_color),
                                  title="Выберите цвет")
        if c[0]:
            self.current_color = tuple(int(x) for x in c[0])
            self.color_preview.configure(bg=c[1])

    def _set_color_hex(self, hex_color):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        self.current_color = (r, g, b)
        self.color_preview.configure(bg=hex_color)

    # --- Drawing ---
    def _cell_from_event(self, event):
        c = max(0, min(event.x // CELL, COLS-1))
        r = max(0, min(event.y // CELL, ROWS-1))
        return r, c

    def _set_pixel(self, r, c, color):
        self.grid_colors[r][c] = color
        self.canvas.itemconfig(self.rects[r][c], fill=self._rgb_to_hex(color))
        self._send_pixel(r, c, color)

    def _on_press(self, e):
        self.drawing = True
        r, c = self._cell_from_event(e)
        self._set_pixel(r, c, self.current_color)

    def _on_drag(self, e):
        if self.drawing:
            r, c = self._cell_from_event(e)
            self._set_pixel(r, c, self.current_color)

    def _on_release(self, e):
        self.drawing = False

    def _on_right_press(self, e):
        self.erasing = True
        r, c = self._cell_from_event(e)
        self._set_pixel(r, c, (0,0,0))

    def _on_right_drag(self, e):
        if self.erasing:
            r, c = self._cell_from_event(e)
            self._set_pixel(r, c, (0,0,0))

    def _on_right_release(self, e):
        self.erasing = False

    # --- Serial ---
    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)

    def _toggle_connect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.serial_conn = None
            self.connect_btn.configure(text="Подключить")
            self.status_label.configure(text="● Отключено", foreground="#ff4444")
        else:
            port = self.port_var.get()
            if not port:
                messagebox.showwarning("Ошибка", "Выберите COM-порт")
                return
            try:
                self.serial_conn = serial.Serial(port, 115200, timeout=1)
                time.sleep(2)  # Wait for ESP32 reset
                self.connect_btn.configure(text="Отключить")
                self.status_label.configure(text=f"● {port}", foreground="#00ff88")
            except Exception as ex:
                messagebox.showerror("Ошибка", f"Не удалось подключиться:\n{ex}")

    def _send_cmd(self, cmd):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write((cmd + "\n").encode())
                self.serial_conn.flush()
            except:
                pass

    def _pixel_index(self, r, c):
        """Convert row/col to LED index. Supports straight and zigzag layouts."""
        if self.zigzag.get() and r % 2 == 1:
            return r * COLS + (COLS - 1 - c)
        return r * COLS + c

    def _send_pixel(self, r, c, color):
        idx = self._pixel_index(r, c)
        self._send_cmd(f"P:{idx},{color[0]},{color[1]},{color[2]}")

    def _send_all(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            messagebox.showwarning("Ошибка", "Нет подключения к ESP32")
            return
        # Send in batches
        batch = []
        for r in range(ROWS):
            for c in range(COLS):
                clr = self.grid_colors[r][c]
                idx = self._pixel_index(r, c)
                batch.append(f"{idx},{clr[0]},{clr[1]},{clr[2]}")
                if len(batch) >= 10:
                    self._send_cmd("BATCH:" + ";".join(batch))
                    batch.clear()
                    time.sleep(0.02)
        if batch:
            self._send_cmd("BATCH:" + ";".join(batch))

    def _clear_all(self):
        for r in range(ROWS):
            for c in range(COLS):
                self.grid_colors[r][c] = (0,0,0)
                self.canvas.itemconfig(self.rects[r][c], fill="#000000")
        self._send_cmd("CLEAR")

    def _fill_all(self):
        clr = self.current_color
        for r in range(ROWS):
            for c in range(COLS):
                self.grid_colors[r][c] = clr
                self.canvas.itemconfig(self.rects[r][c], fill=self._rgb_to_hex(clr))
        self._send_cmd(f"FILL:{clr[0]},{clr[1]},{clr[2]}")

    def _on_brightness(self, val):
        b = int(float(val))
        self.br_label.configure(text=str(b))
        self._send_cmd(f"BRIGHT:{b}")

    # --- Export Arduino Code ---
    def _export_code(self):
        path = filedialog.asksaveasfilename(defaultextension=".ino",
            filetypes=[("Arduino","*.ino"),("All","*.*")],
            initialfile="matrix_pattern.ino")
        if not path:
            return

        lines = ['#include <Adafruit_NeoPixel.h>', '',
                 '#define LED_PIN    48', '#define NUM_LEDS   256',
                 '#define BRIGHTNESS 50', '',
                 'Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);', '',
                 'void setup() {', '  strip.begin();',
                 '  strip.setBrightness(BRIGHTNESS);', '  strip.clear();', '']

        for r in range(ROWS):
            for c in range(COLS):
                clr = self.grid_colors[r][c]
                if clr != (0,0,0):
                    idx = self._pixel_index(r, c)
                    lines.append(f'  strip.setPixelColor({idx}, strip.Color({clr[0]}, {clr[1]}, {clr[2]}));')

        lines += ['', '  strip.show();', '}', '', 'void loop() {', '  // Static pattern', '}', '']

        with open(path, 'w') as f:
            f.write('\n'.join(lines))
        messagebox.showinfo("Готово", f"Код сохранён:\n{path}")

    @staticmethod
    def _rgb_to_hex(rgb):
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

if __name__ == "__main__":
    root = tk.Tk()
    app = MatrixController(root)
    root.mainloop()
