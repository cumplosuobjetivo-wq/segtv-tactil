import csv
import os
import base64
import io
import tempfile
import json
import subprocess
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from tkcalendar import DateEntry
import mysql.connector
import sys
import platform

# Importar configuración
try:
    from config import DB_CONFIG, APP_CONFIG, BACKUP_CONFIG, EXPORT_CONFIG, PDF_CONFIG
except ImportError:
    # Configuración por defecto si no existe config.py
    DB_CONFIG = {
        "host": "127.0.0.1",
        "user": "root",
        "password": "",
        "database": "Reparaciones Telereparo Vigo"
    }
    APP_CONFIG = {
        "window_width": 1366,
        "window_height": 768,
        "min_width": 1200,
        "min_height": 700,
        "title": "SGETV Táctil - Sistema de Gestión de Equipos Telereparo Vigo"
    }
    BACKUP_CONFIG = {
        "default_path": "~/Desktop",
        "filename_prefix": "telereparo_respaldo_"
    }
    EXPORT_CONFIG = {
        "presupuestos_folder": "presupuestos",
        "notas_folder": "notas_entrega"
    }
    PDF_CONFIG = {
        "company_name": "Telereparo Vigo",
        "footer_text": "Sistema de Gestión de Equipos Telereparo Vigo"
    }

# Detectar sistema operativo
SISTEMA = platform.system().lower()

try:
    from logo_embed import LOGO_BASE64
except ImportError:
    LOGO_BASE64 = None

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

#* Configuración de la base de datos
#DB_CONFIG = {
#    "host": "127.0.0.1",
#    "user": "root",
#    "password": "4l3x4ndr4",
#    "database": "Reparaciones Telereparo Vigo",
#}

# Para Debian, verificar si necesitamos socket de MySQL
if SISTEMA == "linux":
    DB_CONFIG["unix_socket"] = "/var/run/mysqld/mysqld.sock"

def conectar():
    """Conecta a la base de datos con configuración para el sistema operativo"""
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        if SISTEMA == "linux" and "unix_socket" in DB_CONFIG:
            config_temp = DB_CONFIG.copy()
            del config_temp["unix_socket"]
            return mysql.connector.connect(**config_temp)
        raise e

class SGETVApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SGETV Táctil - Sistema de Gestión de Equipos Telereparo Vigo")
        self.root.geometry("1366x768")
        self.root.minsize(1200, 700)
        
        if SISTEMA == "linux":
            self.root.state("normal")
            self.root.geometry("1366x768")
        else:
            self.root.state("zoomed")
            
        self.modo_pantalla_completa = False
        self.root.bind("<F11>", self.alternar_pantalla_completa)
        self.root.bind("<Escape>", self.salir_pantalla_completa)
        self.root.bind("<Alt-F4>", self.intentar_cerrar_ventana)
        self.root.protocol("WM_DELETE_WINDOW", self.intentar_cerrar_ventana)

        self.configurar_estilos()

        self.container = ttk.Frame(self.root, style="App.TFrame", padding=14)
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        self.filas_ver = []
        self.id_equipo_tareas = None
        self.eq_nombre_tareas = None
        self.logo_menu_img = None
        self.filtros_activos = {}
        
        if LOGO_BASE64:
            self.logo_menu_path = None
        else:
            self.logo_menu_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "recortado con fondo.png",
            )

        try:
            ruta_logo = self.preparar_logo_menu(self.logo_menu_path)
            if ruta_logo and os.path.exists(ruta_logo):
                self.logo_menu_img = tk.PhotoImage(file=ruta_logo)
                max_ancho_logo = 280
                max_alto_logo = 160
                factor_ancho = max(1, (self.logo_menu_img.width() + max_ancho_logo - 1) // max_ancho_logo)
                factor_alto = max(1, (self.logo_menu_img.height() + max_alto_logo - 1) // max_alto_logo)
                factor = max(factor_ancho, factor_alto)
                if factor > 1:
                    self.logo_menu_img = self.logo_menu_img.subsample(factor, factor)
        except tk.TclError:
            self.logo_menu_img = None

        self.crear_vistas_principales()
        self.mostrar_vista("menu")

        self.btn_kiosco_pantalla = ttk.Button(
            self.root,
            text="Modo quiosco",
            command=self.alternar_pantalla_completa,
            style="TouchUtility.TButton",
        )
        self.btn_kiosco_pantalla.place(relx=0.895, rely=0.955, anchor="se")
        self.btn_kiosco_pantalla.lift()

        self.btn_teclado_pantalla = ttk.Button(
            self.root,
            text="Teclado",
            command=self.abrir_teclado_pantalla,
            style="TouchUtility.TButton",
        )
        self.btn_teclado_pantalla.place(relx=0.985, rely=0.955, anchor="se")
        self.btn_teclado_pantalla.lift()

        self.actualizar_texto_boton_kiosco()

    def actualizar_texto_boton_kiosco(self):
        if hasattr(self, "btn_kiosco_pantalla"):
            texto = "Salir quiosco" if self.modo_pantalla_completa else "Modo quiosco"
            self.btn_kiosco_pantalla.config(text=texto)

    def alternar_pantalla_completa(self, event=None):
        if self.modo_pantalla_completa:
            self.salir_pantalla_completa()
        else:
            self.activar_modo_kiosco()
        return "break"

    def activar_modo_kiosco(self, event=None):
        self.modo_pantalla_completa = True
        if SISTEMA == "linux":
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
        else:
            self.root.state("normal")
            self.root.overrideredirect(False)
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
        self.root.update_idletasks()
        self.actualizar_texto_boton_kiosco()
        return "break"

    def salir_pantalla_completa(self, event=None):
        self.modo_pantalla_completa = False
        if SISTEMA == "linux":
            self.root.attributes("-fullscreen", False)
            self.root.attributes("-topmost", False)
            self.root.state("normal")
        else:
            self.root.attributes("-fullscreen", False)
            self.root.overrideredirect(False)
            self.root.attributes("-topmost", False)
            self.root.state("zoomed")
        self.root.update_idletasks()
        self.actualizar_texto_boton_kiosco()
        return "break"

    def intentar_cerrar_ventana(self, event=None):
        if self.modo_pantalla_completa:
            confirmar = messagebox.askyesno(
                "Modo quiosco",
                "El modo quiosco esta activo.\n\nQuieres salir del modo quiosco y cerrar la aplicacion?",
            )
            if not confirmar:
                return "break"
            self.salir_pantalla_completa()

        confirmar_salida = messagebox.askyesno("Salir", "Quieres cerrar SGETV?")
        if confirmar_salida:
            self.root.destroy()
            return None
        return "break"

    def abrir_teclado_pantalla(self):
        """Abre el teclado virtual según el sistema operativo"""
        errores = []
        era_topmost = bool(self.root.attributes("-topmost"))

        if era_topmost:
            self.root.attributes("-topmost", False)

        if SISTEMA == "linux":
            teclados = ["onboard", "florence", "matchbox-keyboard"]
            for teclado in teclados:
                try:
                    subprocess.Popen([teclado], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if era_topmost:
                        self.root.after(350, lambda: self.root.attributes("-topmost", True))
                    return
                except (subprocess.SubprocessError, FileNotFoundError):
                    continue
            
            messagebox.showinfo("Teclado virtual", 
                "No se encontró un teclado virtual instalado.\n"
                "Puedes instalarlo con: sudo apt install onboard")
            
        else:
            windir = os.environ.get("WINDIR", r"C:\Windows")
            candidatos = [
                os.path.join(windir, "System32", "osk.exe"),
                os.path.join(windir, "Sysnative", "osk.exe"),
                os.path.join(os.environ.get("ProgramFiles", ""), "Common Files", "microsoft shared", "ink", "TabTip.exe"),
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Common Files", "microsoft shared", "ink", "TabTip.exe"),
            ]

            ruta_osk = shutil.which("osk.exe")
            ruta_tabtip = shutil.which("TabTip.exe")
            if ruta_osk:
                candidatos.append(ruta_osk)
            if ruta_tabtip:
                candidatos.append(ruta_tabtip)

            for ejecutable in candidatos:
                if not ejecutable:
                    continue
                try:
                    if os.path.isfile(ejecutable):
                        os.startfile(ejecutable)
                        if era_topmost:
                            self.root.after(350, lambda: self.root.attributes("-topmost", True))
                        return
                except OSError as e:
                    errores.append(str(e))

            comandos_fallback = [
                ["cmd", "/c", "start", "", "osk.exe"],
                ["cmd", "/c", "start", "", "tabtip.exe"],
            ]

            for cmd in comandos_fallback:
                try:
                    subprocess.Popen(cmd, shell=False)
                    if era_topmost:
                        self.root.after(350, lambda: self.root.attributes("-topmost", True))
                    return
                except OSError as e:
                    errores.append(str(e))

        if era_topmost:
            self.root.attributes("-topmost", True)

        if SISTEMA != "linux":
            detalle = errores[-1] if errores else "No se encontró osk.exe ni TabTip.exe"
            messagebox.showerror("SGETV", f"No se pudo abrir el teclado en pantalla.\nDetalle: {detalle}")

    def preparar_logo_menu(self, ruta_logo):
        """Prepara el logo desde archivo o desde Base64 embebido"""
        if LOGO_BASE64:
            try:
                from PIL import Image
                imagen_bytes = base64.b64decode(LOGO_BASE64)
                imagen = Image.open(io.BytesIO(imagen_bytes)).convert("RGBA")
                ancho, alto = imagen.size
                pix = imagen.load()

                muestras_borde = [
                    pix[0, 0],
                    pix[ancho - 1, 0],
                    pix[0, alto - 1],
                    pix[ancho - 1, alto - 1],
                    pix[ancho // 2, 0],
                    pix[ancho // 2, alto - 1],
                    pix[0, alto // 2],
                    pix[ancho - 1, alto // 2],
                ]

                color_fondo = muestras_borde[0] if muestras_borde else pix[0, 0]

                def es_color_similar(color1, color2, tolerancia=30):
                    if len(color1) < 3 or len(color2) < 3:
                        return False
                    return all(abs(c1 - c2) <= tolerancia for c1, c2 in zip(color1[:3], color2[:3]))

                for y in range(alto):
                    for x in range(ancho):
                        if es_color_similar(pix[x, y], color_fondo):
                            pix[x, y] = (*color_fondo[:3], 0) if len(color_fondo) >= 3 else (255, 255, 255, 0)

                archivo_temp = os.path.join(tempfile.gettempdir(), "logo_temp.png")
                imagen.save(archivo_temp, "PNG")
                return archivo_temp
            except Exception:
                pass

        return ruta_logo

    def configurar_estilos(self):
        estilo = ttk.Style()
        estilo.theme_use("clam")

        self.colores_ui = {
            "bg_app": "#07142b",
            "bg_card": "#0b1d36",
            "bg_input": "#102749",
            "bg_input_focus": "#163661",
            "bg_table": "#060f22",
            "bg_table_alt": "#0a1731",
            "bg_table_header": "#12335f",
            "bg_selected": "#1f67bf",
            "fg_text": "#f2f6ff",
            "fg_title": "#f2be3e",
            "fg_subtitle": "#7fb3ff",
            "fg_label": "#d4e5ff",
            "fg_footer": "#8ba4c7",
            "bg_button": "#124785",
            "bg_button_hover": "#1b5fae",
            "bg_button_press": "#0f3a6c",
            "fg_button": "#f2be3e",
            "fg_value": "#ffd76a",
            "grid": "#274771",
        }

        bg_app = self.colores_ui["bg_app"]
        bg_card = self.colores_ui["bg_card"]
        bg_input = self.colores_ui["bg_input"]
        bg_input_focus = self.colores_ui["bg_input_focus"]
        fg_text = self.colores_ui["fg_text"]
        fg_title = self.colores_ui["fg_title"]
        fg_subtitle = self.colores_ui["fg_subtitle"]
        fg_label = self.colores_ui["fg_label"]
        fg_footer = self.colores_ui["fg_footer"]
        bg_button = self.colores_ui["bg_button"]
        bg_button_hover = self.colores_ui["bg_button_hover"]
        bg_button_press = self.colores_ui["bg_button_press"]
        fg_button = self.colores_ui["fg_button"]

        estilo.configure("App.TFrame", background=bg_app, relief="flat")
        estilo.configure("Card.TFrame", background=bg_card, relief="flat")
        estilo.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground=fg_title, background=bg_app)
        estilo.configure("Subtitle.TLabel", font=("Segoe UI", 11), foreground=fg_subtitle, background=bg_app)
        estilo.configure("Field.TLabel", font=("Segoe UI", 10), foreground=fg_label, background=bg_app)
        estilo.configure("Footer.TLabel", font=("Segoe UI", 8), foreground=fg_footer, background=bg_app)
        
        estilo.configure(
            "TButton",
            background=bg_button,
            foreground=fg_button,
            borderwidth=1,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=8
        )
        estilo.map("TButton", 
                  background=[("active", bg_button_hover), ("pressed", bg_button_press)],
                  foreground=[("active", fg_button), ("pressed", fg_button)])

        estilo.configure(
            "TouchUtility.TButton",
            background=bg_button,
            foreground=fg_button,
            borderwidth=1,
            font=("Segoe UI", 12, "bold"),
            relief="groove",
            padding=(14, 10),
        )
        estilo.map(
            "TouchUtility.TButton",
            background=[("active", bg_button_hover), ("pressed", bg_button_press)],
            foreground=[("active", fg_button), ("pressed", fg_button)],
        )

        estilo.configure("TEntry", 
                        fieldbackground=bg_input, 
                        foreground=fg_text, 
                        borderwidth=1, 
                        relief="solid",
                        padding=5)
        estilo.map("TEntry", 
                  fieldbackground=[("focus", bg_input_focus)],
                  foreground=[("focus", fg_text)])

        estilo.configure("TCombobox",
                        fieldbackground=bg_input,
                        foreground=fg_text,
                        borderwidth=1,
                        relief="solid",
                        padding=5)
        estilo.map("TCombobox",
                  fieldbackground=[("focus", bg_input_focus)])

        estilo.configure(
            "Treeview",
            background=self.colores_ui["bg_table"],
            fieldbackground=self.colores_ui["bg_table"],
            foreground=fg_text,
            borderwidth=1,
            relief="solid",
            font=("Segoe UI", 9)
        )
        estilo.configure("Treeview", rowheight=26)
        estilo.map("Treeview", 
                  background=[("selected", self.colores_ui["bg_selected"])], 
                  foreground=[("selected", fg_text)])
        estilo.configure(
            "Treeview.Heading",
            background=self.colores_ui["bg_table_header"],
            foreground=fg_title,
            font=("Segoe UI", 10, "bold"),
            borderwidth=1,
            relief="solid",
        )
        estilo.map(
            "Treeview.Heading",
            background=[("active", self.colores_ui["bg_table_header"])],
            foreground=[("active", fg_title)],
        )

        estilo.configure("TLabelframe",
                        background=bg_app,
                        foreground=fg_title,
                        borderwidth=1)
        estilo.configure("TLabelframe.Label",
                        background=bg_app,
                        foreground=fg_title,
                        font=("Segoe UI", 10, "bold"))

    def crear_panel_base(self):
        panel = ttk.Frame(self.container, style="Card.TFrame", padding=14)
        panel.place(relx=0.5, rely=0.5, relwidth=0.96, relheight=0.94, anchor="center")
        return panel

    def crear_text_field(self, parent, height=4, width=60):
        paleta = getattr(self, "colores_ui", {})
        text_widget = tk.Text(
            parent,
            bg=paleta.get("bg_input", "#102749"),
            fg=paleta.get("fg_text", "#f2f6ff"),
            font=("Segoe UI", 9),
            height=height,
            width=width,
            relief="solid",
            borderwidth=1,
            insertbackground=paleta.get("fg_text", "#f2f6ff")
        )
        return text_widget

    def mostrar_vista(self, nombre):
        for frame in self.frames.values():
            frame.place_forget()
        if nombre in self.frames:
            self.frames[nombre].place(relx=0.5, rely=0.5, relwidth=0.96, relheight=0.94, anchor="center")

            if nombre == "registro":
                self.actualizar_tabla_registro()
            elif nombre == "registros":
                self.cargar_registros_filtrados()
            elif nombre == "presupuestos":
                self.cargar_presupuestos()
            elif nombre == "clientes":
                self.cargar_clientes()
            elif nombre == "estadisticas":
                self.recargar_estadisticas()

    @staticmethod
    def formatear_fecha(valor):
        if isinstance(valor, datetime):
            return valor.strftime("%d-%m-%Y")
        if isinstance(valor, date):
            return valor.strftime("%d-%m-%Y")
        return str(valor)

    @staticmethod
    def formatear_importe(valor):
        try:
            return f"{float(valor):.2f}"
        except (TypeError, ValueError):
            return str(valor)

    def crear_vistas_principales(self):
        self.crear_menu_principal()
        self.crear_vista_registro()
        self.crear_vista_registros()
        self.crear_vista_presupuestos()
        self.crear_vista_conexion()
        self.crear_vista_tareas()
        self.crear_vista_clientes()
        self.crear_vista_estadisticas()
        self.crear_vista_respaldo()

    def crear_menu_principal(self):
        panel = self.crear_panel_base()

        ttk.Label(
            panel,
            text="Sistema de Gestión de Equipos Telereparo Vigo",
            style="Title.TLabel"
        ).pack(pady=(20, 8))

        if self.logo_menu_img is not None:
            self.lbl_logo_menu = tk.Label(
                panel,
                image=self.logo_menu_img,
                bg=self.colores_ui["bg_app"],
                bd=0,
                highlightthickness=0,
            )
            self.lbl_logo_menu.pack(pady=(2, 12))

        ttk.Label(
            panel,
            text="Seleccione una opción (modo táctil)",
            style="Subtitle.TLabel"
        ).pack(pady=(0, 20))

        centro = ttk.Frame(panel, style="Card.TFrame")
        centro.pack(fill="both", expand=True, padx=28, pady=12)

        estilo = ttk.Style()
        estilo.configure(
            "Menu.TButton",
            font=("Segoe UI", 18, "bold"),
            foreground=self.colores_ui["fg_button"],
            background=self.colores_ui["bg_button"],
            borderwidth=1,
            relief="groove",
            padding=(26, 22)
        )
        estilo.map(
            "Menu.TButton",
            background=[("active", self.colores_ui["bg_button_hover"]), ("pressed", self.colores_ui["bg_button_press"])],
            foreground=[("active", self.colores_ui["fg_button"]), ("pressed", self.colores_ui["fg_button"])],
        )

        botones = [
            ("Registrar equipos", lambda: self.mostrar_vista("registro")),
            ("Ver registros", lambda: self.mostrar_vista("registros")),
            ("Ver presupuestos", lambda: self.mostrar_vista("presupuestos")),
            ("Gestión de clientes", lambda: self.mostrar_vista("clientes")),
            ("Estadísticas", lambda: self.mostrar_vista("estadisticas")),
            ("Respaldo de base de datos", lambda: self.mostrar_vista("respaldo")),
            ("Comprobar conexión", lambda: self.mostrar_vista("conexion")),
            ("Salir", self.intentar_cerrar_ventana),
        ]

        for idx, (texto, comando) in enumerate(botones):
            fila = idx // 2
            columna = idx % 2
            ttk.Button(
                centro,
                text=texto,
                command=comando,
                style="Menu.TButton",
                width=24
            ).grid(row=fila, column=columna, padx=18, pady=16, sticky="nsew")

        centro.columnconfigure(0, weight=1, uniform="menu")
        centro.columnconfigure(1, weight=1, uniform="menu")
        total_filas = (len(botones) + 1) // 2
        for fila in range(total_filas):
            centro.rowconfigure(fila, weight=1, uniform="menu")

        ttk.Button(panel, text="Activar modo kiosco", command=self.activar_modo_kiosco, style="TButton").pack(pady=(4, 6))
        ttk.Label(panel, text="Atajos: F11 activar/desactivar modo kiosco | Esc salir de modo kiosco", style="Subtitle.TLabel").pack(pady=(0, 6))
        ttk.Label(panel, text="© Gabriel Carbon Garcia 2026 Vigo", style="Footer.TLabel").pack(side="bottom", pady=(6, 8))

        self.frames["menu"] = panel

    def crear_vista_registro(self):
        panel = self.crear_panel_base()

        ttk.Label(panel, text="Registrar equipos", style="Title.TLabel").pack(anchor="w", padx=8, pady=(4, 10))

        frame_top = ttk.LabelFrame(panel, text=" Información del Equipo ", padding=10)
        frame_top.pack(fill="x", padx=8, pady=8)

        ttk.Label(frame_top, text="Cliente:", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self.combo_cliente_nuevo = ttk.Combobox(frame_top, width=30, state="readonly")
        self.combo_cliente_nuevo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame_top, text="Equipo:", style="Field.TLabel").grid(row=1, column=0, sticky="w")
        self.txt_eqp = ttk.Entry(frame_top, width=32)
        self.txt_eqp.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame_top, text="Marca:", style="Field.TLabel").grid(row=0, column=2, sticky="w")
        self.txt_marca = ttk.Entry(frame_top, width=20)
        self.txt_marca.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(frame_top, text="Modelo:", style="Field.TLabel").grid(row=1, column=2, sticky="w")
        self.txt_modelo = ttk.Entry(frame_top, width=20)
        self.txt_modelo.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(frame_top, text="Categoría:", style="Field.TLabel").grid(row=2, column=0, sticky="w")
        self.combo_categoria = ttk.Combobox(frame_top, state="readonly", values=["Móvil", "Tablet", "Laptop", "PC", "Periférico", "Otro"])
        self.combo_categoria.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(frame_top, text="Diagnóstico:", style="Field.TLabel").grid(row=2, column=2, sticky="nw")
        self.txt_diagnostico = self.crear_text_field(frame_top, height=3, width=25)
        self.txt_diagnostico.grid(row=2, column=3, padx=5, pady=5)

        ttk.Label(frame_top, text="Garantía (días):", style="Field.TLabel").grid(row=3, column=0, sticky="w")
        self.txt_garantia = ttk.Entry(frame_top, width=10)
        self.txt_garantia.grid(row=3, column=1, padx=5, pady=5)
        self.txt_garantia.insert(0, "30")

        btn_frame = ttk.Frame(panel, style="Card.TFrame")
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Button(btn_frame, text="Guardar Entrada", command=self.registrar_equipo).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Borrar Seleccionado", command=self.eliminar_registro).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Editar Equipo", command=self.editar_equipo_seleccionado).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Refrescar Tabla", command=self.actualizar_tabla_registro).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Volver al menú principal", command=lambda: self.mostrar_vista("menu")).pack(side="right", padx=5)

        frame_tabla = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 8))
        frame_tabla.pack(fill="both", expand=True)

        self.tabla_registro = ttk.Treeview(
            frame_tabla,
            columns=("ID", "Fecha", "Equipo", "Marca", "Modelo", "Cliente", "Categoría", "Estado", "F.Salida"),
            show="headings"
        )
        self.tabla_registro.heading("ID", text="Nº TICKET")
        self.tabla_registro.heading("Fecha", text="ENTRADA")
        self.tabla_registro.heading("Equipo", text="EQUIPO")
        self.tabla_registro.heading("Marca", text="MARCA")
        self.tabla_registro.heading("Modelo", text="MODELO")
        self.tabla_registro.heading("Cliente", text="CLIENTE")
        self.tabla_registro.heading("Categoría", text="CATEGORÍA")
        self.tabla_registro.heading("Estado", text="ESTADO")
        self.tabla_registro.heading("F.Salida", text="SALIDA")

        self.tabla_registro.column("ID", width=60, anchor="center")
        self.tabla_registro.column("Fecha", width=80, anchor="center")
        self.tabla_registro.column("Equipo", width=120)
        self.tabla_registro.column("Marca", width=80)
        self.tabla_registro.column("Modelo", width=100)
        self.tabla_registro.column("Cliente", width=100)
        self.tabla_registro.column("Categoría", width=80)
        self.tabla_registro.column("Estado", width=80)
        self.tabla_registro.column("F.Salida", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tabla_registro.yview)
        self.tabla_registro.configure(yscrollcommand=scrollbar.set)
        self.tabla_registro.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tabla_registro.bind("<Double-1>", self.abrir_editar_tareas)

        self.frames["registro"] = panel
        self.cargar_combo_clientes(self.combo_cliente_nuevo)

    def crear_vista_registros(self):
        panel = self.crear_panel_base()

        ttk.Label(panel, text="Ver registros", style="Title.TLabel").pack(anchor="w", padx=8, pady=(4, 10))

        frame_superior = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 10))
        frame_superior.pack(fill="x")

        self.lbl_total = ttk.Label(frame_superior, text="Total de registros: 0", style="Subtitle.TLabel")
        self.lbl_total.pack(side="left")

        btn_frame_top = ttk.Frame(frame_superior, style="Card.TFrame")
        btn_frame_top.pack(side="right")
        ttk.Button(btn_frame_top, text="Exportar CSV", command=self.exportar_csv).pack(side="left", padx=5)
        ttk.Button(btn_frame_top, text="Exportar PDF", command=self.exportar_pdf).pack(side="left", padx=5)
        ttk.Button(btn_frame_top, text="Generar Nota", command=self.generar_nota_manual).pack(side="left", padx=5)
        ttk.Button(btn_frame_top, text="Refrescar", command=self.cargar_registros_filtrados).pack(side="left", padx=5)
        ttk.Button(btn_frame_top, text="Volver al menú", command=lambda: self.mostrar_vista("menu")).pack(side="left", padx=5)

        frame_filtros = ttk.LabelFrame(panel, text=" Filtros Avanzados ", padding=10)
        frame_filtros.pack(fill="x", padx=8, pady=8)

        ttk.Label(frame_filtros, text="Número de Ticket:", style="Field.TLabel").grid(row=0, column=0, sticky="w", padx=5)
        self.filtro_ticket = ttk.Entry(frame_filtros, width=12)
        self.filtro_ticket.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame_filtros, text="Equipo:", style="Field.TLabel").grid(row=0, column=2, sticky="w", padx=5)
        self.filtro_equipo = ttk.Entry(frame_filtros, width=25)
        self.filtro_equipo.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(frame_filtros, text="Cliente:", style="Field.TLabel").grid(row=1, column=0, sticky="w", padx=5)
        self.filtro_cliente = ttk.Entry(frame_filtros, width=25)
        self.filtro_cliente.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame_filtros, text="Marca/Modelo:", style="Field.TLabel").grid(row=1, column=2, sticky="w", padx=5)
        self.filtro_marca = ttk.Entry(frame_filtros, width=25)
        self.filtro_marca.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(frame_filtros, text="Fecha desde:", style="Field.TLabel").grid(row=2, column=0, sticky="w", padx=5)
        self.filtro_fecha_desde = DateEntry(frame_filtros, width=15)
        self.filtro_fecha_desde.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(frame_filtros, text="Fecha hasta:", style="Field.TLabel").grid(row=2, column=2, sticky="w", padx=5)
        self.filtro_fecha_hasta = DateEntry(frame_filtros, width=15)
        self.filtro_fecha_hasta.grid(row=2, column=3, padx=5, pady=5)

        ttk.Label(frame_filtros, text="Precio desde:", style="Field.TLabel").grid(row=3, column=0, sticky="w", padx=5)
        self.filtro_precio_desde = ttk.Entry(frame_filtros, width=12)
        self.filtro_precio_desde.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(frame_filtros, text="Precio hasta:", style="Field.TLabel").grid(row=3, column=2, sticky="w", padx=5)
        self.filtro_precio_hasta = ttk.Entry(frame_filtros, width=12)
        self.filtro_precio_hasta.grid(row=3, column=3, padx=5, pady=5)

        ttk.Label(frame_filtros, text="Estado:", style="Field.TLabel").grid(row=4, column=0, sticky="w", padx=5)
        self.filtro_estado = ttk.Combobox(frame_filtros, width=20, state="readonly", 
                                         values=["", "Pendiente", "En progreso", "Pausada", "Completada", "Entregada", "Rechazada"])
        self.filtro_estado.grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(frame_filtros, text="Categoría:", style="Field.TLabel").grid(row=4, column=2, sticky="w", padx=5)
        self.filtro_categoria = ttk.Combobox(frame_filtros, width=20, state="readonly",
                                            values=["", "Móvil", "Tablet", "Laptop", "PC", "Periférico", "Otro"])
        self.filtro_categoria.grid(row=4, column=3, padx=5, pady=5)

        btn_filtro_frame = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 8))
        btn_filtro_frame.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Button(btn_filtro_frame, text="Aplicar Filtros", command=self.cargar_registros_filtrados).pack(side="left", padx=5)
        ttk.Button(btn_filtro_frame, text="Limpiar Filtros", command=self.limpiar_filtros).pack(side="left", padx=5)

        frame_tabla = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 8))
        frame_tabla.pack(fill="both", expand=True)

        self.tabla_ver = ttk.Treeview(
            frame_tabla,
            columns=("id", "fecha", "equipo", "marca", "modelo", "cliente", "categoria", "estado", "f_salida", "importe"),
            show="headings"
        )
        self.tabla_ver.heading("id", text="ID")
        self.tabla_ver.heading("fecha", text="Entrada")
        self.tabla_ver.heading("equipo", text="Equipo")
        self.tabla_ver.heading("marca", text="Marca")
        self.tabla_ver.heading("modelo", text="Modelo")
        self.tabla_ver.heading("cliente", text="Cliente")
        self.tabla_ver.heading("categoria", text="Categoría")
        self.tabla_ver.heading("estado", text="Estado")
        self.tabla_ver.heading("f_salida", text="Salida")
        self.tabla_ver.heading("importe", text="Importe (€)")

        self.tabla_ver.column("id", width=50, anchor="center")
        self.tabla_ver.column("fecha", width=70, anchor="center")
        self.tabla_ver.column("equipo", width=100)
        self.tabla_ver.column("marca", width=70)
        self.tabla_ver.column("modelo", width=80)
        self.tabla_ver.column("cliente", width=100)
        self.tabla_ver.column("categoria", width=70)
        self.tabla_ver.column("estado", width=80)
        self.tabla_ver.column("f_salida", width=70, anchor="center")
        self.tabla_ver.column("importe", width=80, anchor="e")

        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tabla_ver.yview)
        self.tabla_ver.configure(yscrollcommand=scrollbar.set)
        self.tabla_ver.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.frames["registros"] = panel

    def crear_vista_presupuestos(self):
        panel = self.crear_panel_base()

        ttk.Label(panel, text="Ver Presupuestos", style="Title.TLabel").pack(anchor="w", padx=8, pady=(4, 10))

        btn_frame = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 10))
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="Exportar Presupuesto", command=self.exportar_presupuesto).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Aceptar Presupuesto", command=self.aceptar_presupuesto).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Rechazar Presupuesto", command=self.rechazar_presupuesto).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Refrescar", command=self.cargar_presupuestos).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Volver al menú", command=lambda: self.mostrar_vista("menu")).pack(side="left", padx=5)

        frame_tabla = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 8))
        frame_tabla.pack(fill="both", expand=True)

        self.tabla_presupuestos = ttk.Treeview(
            frame_tabla,
            columns=("id", "ticket", "descripcion", "importe", "fecha", "aceptado"),
            show="headings"
        )
        self.tabla_presupuestos.heading("id", text="ID Presupuesto")
        self.tabla_presupuestos.heading("ticket", text="Nº Ticket")
        self.tabla_presupuestos.heading("descripcion", text="Descripción")
        self.tabla_presupuestos.heading("importe", text="Importe (€)")
        self.tabla_presupuestos.heading("fecha", text="Fecha")
        self.tabla_presupuestos.heading("aceptado", text="Aceptado")

        self.tabla_presupuestos.column("id", width=60, anchor="center")
        self.tabla_presupuestos.column("ticket", width=80, anchor="center")
        self.tabla_presupuestos.column("descripcion", width=400)
        self.tabla_presupuestos.column("importe", width=100, anchor="e")
        self.tabla_presupuestos.column("fecha", width=100, anchor="center")
        self.tabla_presupuestos.column("aceptado", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tabla_presupuestos.yview)
        self.tabla_presupuestos.configure(yscrollcommand=scrollbar.set)
        self.tabla_presupuestos.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.tabla_presupuestos.bind("<Double-1>", lambda e: self.mostrar_ventana_presupuesto())

        self.frames["presupuestos"] = panel

    def mostrar_ventana_presupuesto(self):
        """Abre una ventana con el presupuesto seleccionado"""
        seleccionado = self.tabla_presupuestos.selection()
        if not seleccionado:
            messagebox.showwarning("Advertencia", "Selecciona un presupuesto primero")
            return

        item = seleccionado[0]
        valores = self.tabla_presupuestos.item(item, "values")
        id_presupuesto = valores[0]
        id_rep = valores[1]

        try:
            db = conectar()
            cursor = db.cursor()

            cursor.execute("""
                SELECT p.id_presupuesto, p.id_rep, p.descripcion_trabajo, 
                       p.importe_estimado, p.fecha_presupuesto, p.aceptado,
                       rd.nb_eqp, rd.marca_equipo, rd.modelo_equipo,
                       c.nombre as cliente_nombre, c.telefono, c.email, c.direccion
                FROM presupuestos p
                JOIN recepciones_despachos rd ON p.id_rep = rd.id_rep
                LEFT JOIN clientes c ON rd.id_cliente = c.id_cli
                WHERE p.id_presupuesto = %s
            """, (id_presupuesto,))

            presupuesto = cursor.fetchone()
            cursor.close()
            db.close()

            if not presupuesto:
                messagebox.showerror("Error", "No se encontró el presupuesto")
                return

            (id_presupuesto, id_rep, descripcion, importe, fecha_pres, aceptado,
             equipo, marca, modelo, cliente, telefono, email, direccion) = presupuesto

            ventana = tk.Toplevel(self.root)
            ventana.title(f"Presupuesto #{id_presupuesto} - Ticket #{id_rep}")
            ventana.geometry("600x700")
            
            ventana.update_idletasks()
            ventana.update()
            
            ventana.grab_set()
            ventana.attributes('-topmost', True)
            ventana.lift()
            ventana.focus_force()
            
            ventana.update()
            x = (ventana.winfo_screenwidth() - 600) // 2
            y = (ventana.winfo_screenheight() - 700) // 2
            ventana.geometry(f"600x700+{x}+{y}")

            container = ttk.Frame(ventana, padding=15)
            container.pack(fill="both", expand=True)

            lbl_titulo = ttk.Label(container, text="PRESUPUESTO", style="Title.TLabel")
            lbl_titulo.pack(pady=(0, 10))

            lbl_info = ttk.Label(container, text=f"Ticket: #{id_rep} | Presupuesto: #{id_presupuesto}")
            lbl_info.pack(pady=(0, 15))

            frame_content = ttk.Frame(container, style="Card.TFrame")
            frame_content.pack(fill="both", expand=True)

            canvas = tk.Canvas(frame_content, bg=self.colores_ui["bg_card"], highlightthickness=0)
            scrollbar = ttk.Scrollbar(frame_content, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            ttk.Label(scrollable_frame, text="CLIENTE", style="Subtitle.TLabel").pack(anchor="w", pady=(10, 5))
            ttk.Label(scrollable_frame, text=f"Nombre: {cliente if cliente else 'No especificado'}").pack(anchor="w", padx=10)
            ttk.Label(scrollable_frame, text=f"Teléfono: {telefono if telefono else 'N/A'}").pack(anchor="w", padx=10)
            ttk.Label(scrollable_frame, text=f"Email: {email if email else 'N/A'}").pack(anchor="w", padx=10)
            ttk.Label(scrollable_frame, text=f"Dirección: {direccion if direccion else 'N/A'}").pack(anchor="w", padx=10)

            ttk.Separator(scrollable_frame, orient="horizontal").pack(fill="x", pady=10)

            ttk.Label(scrollable_frame, text="EQUIPO", style="Subtitle.TLabel").pack(anchor="w", pady=(10, 5))
            ttk.Label(scrollable_frame, text=f"Equipo: {equipo if equipo else 'No especificado'}").pack(anchor="w", padx=10)
            ttk.Label(scrollable_frame, text=f"Marca: {marca if marca else 'N/A'}").pack(anchor="w", padx=10)
            ttk.Label(scrollable_frame, text=f"Modelo: {modelo if modelo else 'N/A'}").pack(anchor="w", padx=10)

            ttk.Separator(scrollable_frame, orient="horizontal").pack(fill="x", pady=10)

            ttk.Label(scrollable_frame, text="DESCRIPCIÓN DEL TRABAJO", style="Subtitle.TLabel").pack(anchor="w", pady=(10, 5))
            txt_desc = tk.Text(scrollable_frame, height=6, width=55, wrap="word", 
                              bg=self.colores_ui["bg_input"], fg=self.colores_ui["fg_text"])
            txt_desc.pack(padx=10, pady=5, fill="x")
            txt_desc.insert("1.0", descripcion if descripcion else "No especificada")
            txt_desc.config(state="disabled")

            ttk.Separator(scrollable_frame, orient="horizontal").pack(fill="x", pady=10)

            ttk.Label(scrollable_frame, text="IMPORTE Y ESTADO", style="Subtitle.TLabel").pack(anchor="w", pady=(10, 5))
            importe_formato = f"{float(importe):.2f}" if importe else "0.00"
            ttk.Label(scrollable_frame, text=f"Importe: € {importe_formato}", 
                     style="Title.TLabel", foreground=self.colores_ui["fg_value"]).pack(anchor="w", padx=10)
            aceptado_texto = "Sí" if aceptado else "No"
            ttk.Label(scrollable_frame, text=f"Aceptado: {aceptado_texto}").pack(anchor="w", padx=10)
            
            if isinstance(fecha_pres, datetime):
                fecha_str = fecha_pres.strftime("%d/%m/%Y")
            else:
                fecha_str = str(fecha_pres) if fecha_pres else "N/A"
            ttk.Label(scrollable_frame, text=f"Fecha: {fecha_str}").pack(anchor="w", padx=10)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            frame_botones = ttk.Frame(container)
            frame_botones.pack(fill="x", pady=15)

            if not aceptado:
                ttk.Button(frame_botones, text="Aceptar", 
                          command=lambda: self._aceptar_desde_ventana(id_presupuesto, ventana)).pack(side="left", padx=5)
                ttk.Button(frame_botones, text="Rechazar", 
                          command=lambda: self._rechazar_desde_ventana(id_presupuesto, ventana)).pack(side="left", padx=5)
            
            ttk.Button(frame_botones, text="Exportar PDF", 
                      command=lambda: self._exportar_desde_ventana(id_presupuesto)).pack(side="left", padx=5)
            ttk.Button(frame_botones, text="Cerrar", command=ventana.destroy).pack(side="right", padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Error al abrir presupuesto: {e}")
            import traceback
            traceback.print_exc()

    def _aceptar_desde_ventana(self, id_presupuesto, ventana):
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute(
                "UPDATE presupuestos SET aceptado = TRUE, fecha_aceptacion = NOW() WHERE id_presupuesto = %s",
                (id_presupuesto,)
            )
            db.commit()
            self.registrar_auditoria(db, "presupuestos", int(id_presupuesto), "UPDATE", None, {"aceptado": True})
            db.close()
            
            messagebox.showinfo("Éxito", "Presupuesto aceptado correctamente")
            ventana.destroy()
            self.cargar_presupuestos()
        except Exception as e:
            messagebox.showerror("Error", f"Error al aceptar presupuesto: {e}")

    def _rechazar_desde_ventana(self, id_presupuesto, ventana):
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute(
                "UPDATE presupuestos SET aceptado = FALSE WHERE id_presupuesto = %s",
                (id_presupuesto,)
            )
            db.commit()
            self.registrar_auditoria(db, "presupuestos", int(id_presupuesto), "UPDATE", None, {"aceptado": False})
            db.close()
            
            messagebox.showinfo("Éxito", "Presupuesto rechazado")
            ventana.destroy()
            self.cargar_presupuestos()
        except Exception as e:
            messagebox.showerror("Error", f"Error al rechazar presupuesto: {e}")

    def _exportar_desde_ventana(self, id_presupuesto):
        try:
            db = conectar()
            cursor = db.cursor()

            cursor.execute("""
                SELECT p.id_presupuesto, p.id_rep, p.descripcion_trabajo, 
                       p.importe_estimado, p.fecha_presupuesto,
                       rd.nb_eqp, rd.marca_equipo, rd.modelo_equipo,
                       c.nombre as cliente_nombre, c.telefono, c.email, c.direccion
                FROM presupuestos p
                JOIN recepciones_despachos rd ON p.id_rep = rd.id_rep
                LEFT JOIN clientes c ON rd.id_cliente = c.id_cli
                WHERE p.id_presupuesto = %s
            """, (id_presupuesto,))

            presupuesto = cursor.fetchone()
            cursor.close()
            db.close()

            if not presupuesto:
                messagebox.showerror("Error", "Presupuesto no encontrado")
                return

            id_presupuesto, id_rep, descripcion, importe, fecha_pres, equipo, marca, modelo, cliente, telefono, email, direccion = presupuesto

            if isinstance(fecha_pres, datetime):
                fecha_presupuesto = fecha_pres
            else:
                fecha_presupuesto = datetime.strptime(str(fecha_pres), "%Y-%m-%d")
            
            fecha_validez = fecha_presupuesto + timedelta(days=15)

            from fpdf import FPDF

            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.add_page()

            font_regular, font_bold = self._configurar_fuentes_pdf(pdf)

            pdf.set_font(font_bold, "", 18)
            pdf.set_text_color(242, 190, 62)
            pdf.cell(0, 10, "PRESUPUESTO", 0, 1, "C")
            
            pdf.set_font(font_regular, "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"Ticket: #{id_rep} | Presupuesto: #{id_presupuesto}", 0, 1, "C")
            pdf.ln(5)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "CLIENTE:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, cliente if cliente else "No especificado", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "TELEFONO:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, telefono if telefono else "N/A", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "EMAIL:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, email if email else "N/A", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "DIRECCION:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, direccion if direccion else "N/A", 0, 1)

            pdf.ln(5)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "EQUIPO:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, equipo if equipo else "No especificado", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "MARCA:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, marca if marca else "N/A", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "MODELO:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, modelo if modelo else "N/A", 0, 1)

            pdf.ln(5)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(0, 6, "TAREA A REALIZAR:", 0, 1)
            pdf.set_font(font_regular, "", 10)
            pdf.set_left_margin(10)
            pdf.multi_cell(190, 5, descripcion if descripcion else "No especificada")
            pdf.set_left_margin(10)

            pdf.ln(5)

            pdf.set_font(font_bold, "", 14)
            pdf.set_text_color(242, 190, 62)
            pdf.cell(120, 8, "IMPORTE TOTAL:")
            pdf.cell(0, 8, f"{float(importe):.2f} EUR", 0, 1, "R")

            pdf.set_text_color(0, 0, 0)
            pdf.ln(5)

            pdf.set_font(font_bold, "", 10)
            fecha_emisión = fecha_presupuesto.strftime("%d/%m/%Y")
            fecha_vencimiento = fecha_validez.strftime("%d/%m/%Y")
            
            pdf.cell(80, 6, f"Fecha del Presupuesto: {fecha_emisión}")
            pdf.cell(0, 6, f"Valido hasta: {fecha_vencimiento}", 0, 1)

            pdf.ln(5)

            pdf.set_font(font_regular, "I", 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, "Sistema de Gestion de Equipos Telereparo Vigo", 0, 1, "C")
            pdf.cell(0, 5, "Este presupuesto tiene validez de 15 dias naturales desde su fecha de emision", 0, 1, "C")

            carpeta_presupuestos = "presupuestos"
            if not os.path.exists(carpeta_presupuestos):
                os.makedirs(carpeta_presupuestos)

            cliente_limpio = cliente.replace("/", "-").replace("\\", "-") if cliente else "Cliente"
            equipo_limpio = equipo.replace("/", "-").replace("\\", "-") if equipo else "Equipo"
            
            nombre_archivo = f"{carpeta_presupuestos}/Presupuesto {cliente_limpio} {equipo_limpio}.pdf"
            pdf.output(nombre_archivo)

            messagebox.showinfo("Éxito", f"Presupuesto exportado:\n{nombre_archivo}")

            import subprocess
            subprocess.Popen([nombre_archivo], shell=True)

        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar presupuesto: {e}")
            import traceback
            traceback.print_exc()

    def cargar_presupuestos(self):
        for item in self.tabla_presupuestos.get_children():
            self.tabla_presupuestos.delete(item)

        try:
            db = conectar()
            cursor = db.cursor()

            cursor.execute("""
                SELECT p.id_presupuesto, p.id_rep, p.descripcion_trabajo, 
                       p.importe_estimado, p.fecha_presupuesto, p.aceptado
                FROM presupuestos p
                ORDER BY p.fecha_presupuesto DESC
            """)

            for presupuesto in cursor.fetchall():
                id_presupuesto, id_rep, descripcion, importe, fecha, aceptado = presupuesto
                fecha_formateada = self.formatear_fecha(fecha) if fecha else ""
                aceptado_texto = "Sí" if aceptado else "No"
                importe_formateado = self.formatear_importe(importe) if importe else "0.00"

                self.tabla_presupuestos.insert(
                    "", "end",
                    values=(id_presupuesto, id_rep, descripcion, importe_formateado, fecha_formateada, aceptado_texto)
                )

            cursor.close()
            db.close()

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar presupuestos: {e}")

    def _configurar_fuentes_pdf(self, pdf):
        if SISTEMA == "linux":
            posibles_fuentes = [
                ("DejaVu", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
                ("Noto", "NotoSans-Regular.ttf", "NotoSans-Bold.ttf"),
                ("Liberation", "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf")
            ]
            
            for nombre, regular, bold in posibles_fuentes:
                try:
                    pdf.add_font(nombre, "", regular)
                    pdf.add_font(nombre, "B", bold)
                    return (nombre, nombre)
                except Exception:
                    continue
        
        try:
            pdf.add_font("DejaVu", "", "DejaVuSans.ttf")
            pdf.add_font("DejaVuB", "B", "DejaVuSans-Bold.ttf")
            return ("DejaVu", "DejaVuB")
        except Exception:
            try:
                pdf.add_font("DejaVu", "", "Helvetica")
                pdf.add_font("DejaVuB", "B", "Helvetica-Bold")
                return ("DejaVu", "DejaVuB")
            except Exception:
                return ("Helvetica", "Helvetica")

    def aceptar_presupuesto(self):
        seleccionado = self.tabla_presupuestos.selection()
        if not seleccionado:
            messagebox.showwarning("Advertencia", "Selecciona un presupuesto primero")
            return

        item = seleccionado[0]
        valores = self.tabla_presupuestos.item(item, "values")
        id_presupuesto = valores[0]
        id_rep = valores[1]

        try:
            db = conectar()
            cursor = db.cursor()

            cursor.execute(
                "UPDATE presupuestos SET aceptado = TRUE, fecha_aceptacion = NOW() WHERE id_presupuesto = %s",
                (id_presupuesto,)
            )
            db.commit()

            self.registrar_auditoria(db, "presupuestos", int(id_presupuesto), "UPDATE", None, {"aceptado": True})

            cursor.close()
            db.close()

            respuesta = messagebox.askyesno(
                "Presupuesto aceptado",
                f"Presupuesto {id_presupuesto} aceptado correctamente.\n\n¿Deseas generar la nota de entrega ahora?",
            )
            
            if respuesta:
                self.generar_factura(int(id_rep), int(id_presupuesto))

            self.cargar_presupuestos()

        except Exception as e:
            messagebox.showerror("Error", f"Error al aceptar presupuesto: {e}")

    def rechazar_presupuesto(self):
        seleccionado = self.tabla_presupuestos.selection()
        if not seleccionado:
            messagebox.showwarning("Advertencia", "Selecciona un presupuesto primero")
            return

        item = seleccionado[0]
        id_presupuesto = self.tabla_presupuestos.item(item, "values")[0]

        try:
            db = conectar()
            cursor = db.cursor()

            cursor.execute(
                "UPDATE presupuestos SET aceptado = FALSE WHERE id_presupuesto = %s",
                (id_presupuesto,)
            )
            db.commit()

            self.registrar_auditoria(db, "presupuestos", int(id_presupuesto), "UPDATE", None, {"aceptado": False})

            cursor.close()
            db.close()

            messagebox.showinfo("Exito", f"Presupuesto {id_presupuesto} rechazado")
            self.cargar_presupuestos()

        except Exception as e:
            messagebox.showerror("Error", f"Error al rechazar presupuesto: {e}")

    def exportar_presupuesto(self):
        seleccionado = self.tabla_presupuestos.selection()
        if not seleccionado:
            messagebox.showwarning("Advertencia", "Selecciona un presupuesto primero")
            return

        item = seleccionado[0]
        valores = self.tabla_presupuestos.item(item, "values")
        id_presupuesto = valores[0]
        id_rep = valores[1]

        try:
            db = conectar()
            cursor = db.cursor()

            cursor.execute("""
                SELECT p.id_presupuesto, p.id_rep, p.descripcion_trabajo, 
                       p.importe_estimado, p.fecha_presupuesto,
                       rd.nb_eqp, rd.marca_equipo, rd.modelo_equipo,
                       c.nombre as cliente_nombre, c.telefono, c.email, c.direccion
                FROM presupuestos p
                JOIN recepciones_despachos rd ON p.id_rep = rd.id_rep
                LEFT JOIN clientes c ON rd.id_cliente = c.id_cli
                WHERE p.id_presupuesto = %s
            """, (id_presupuesto,))

            presupuesto = cursor.fetchone()
            if not presupuesto:
                messagebox.showerror("Error", "No se encontró el presupuesto")
                return

            id_presupuesto, id_rep, descripcion, importe, fecha_pres, equipo, marca, modelo, cliente, telefono, email, direccion = presupuesto

            if isinstance(fecha_pres, datetime):
                fecha_presupuesto = fecha_pres
            else:
                fecha_presupuesto = datetime.strptime(str(fecha_pres), "%Y-%m-%d")
            
            fecha_validez = fecha_presupuesto + timedelta(days=15)

            from fpdf import FPDF

            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.add_page()
            
            try:
                if LOGO_BASE64:
                    from PIL import Image
                    imagen_bytes = base64.b64decode(LOGO_BASE64)
                    imagen = Image.open(io.BytesIO(imagen_bytes)).convert("RGBA")
                    ancho, alto = imagen.size
                    pix = imagen.load()

                    muestras_borde = [
                        pix[0, 0],
                        pix[ancho - 1, 0],
                        pix[0, alto - 1],
                        pix[ancho - 1, alto - 1],
                        pix[ancho // 2, 0],
                        pix[ancho // 2, alto - 1],
                        pix[0, alto // 2],
                        pix[ancho - 1, alto // 2],
                    ]

                    color_fondo = muestras_borde[0] if muestras_borde else pix[0, 0]

                    def es_color_similar(color1, color2, tolerancia=30):
                        if len(color1) < 3 or len(color2) < 3:
                            return False
                        return all(abs(c1 - c2) <= tolerancia for c1, c2 in zip(color1[:3], color2[:3]))

                    for y in range(alto):
                        for x in range(ancho):
                            if es_color_similar(pix[x, y], color_fondo):
                                pix[x, y] = (*color_fondo[:3], 0) if len(color_fondo) >= 3 else (255, 255, 255, 0)

                    archivo_temp_logo = os.path.join(tempfile.gettempdir(), "logo_presupuesto.png")
                    imagen.save(archivo_temp_logo, "PNG")
                    
                    ancho_logo = 40
                    pdf.image(archivo_temp_logo, x=160, y=8, w=ancho_logo)
            except Exception:
                pass
            
            font_regular, font_bold = self._configurar_fuentes_pdf(pdf)

            pdf.set_font(font_bold, "", 18)
            pdf.set_text_color(242, 190, 62)
            pdf.cell(0, 10, "PRESUPUESTO", 0, 1, "C")
            
            pdf.set_font(font_regular, "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"Ticket: #{id_rep} | Presupuesto: #{id_presupuesto}", 0, 1, "C")
            pdf.ln(5)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "CLIENTE:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, cliente if cliente else "No especificado", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "TELEFONO:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, telefono if telefono else "N/A", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "EMAIL:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, email if email else "N/A", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "DIRECCION:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, direccion if direccion else "N/A", 0, 1)

            pdf.ln(5)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "EQUIPO:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, equipo if equipo else "No especificado", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "MARCA:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, marca if marca else "N/A", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "MODELO:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, modelo if modelo else "N/A", 0, 1)

            pdf.ln(5)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(0, 6, "TAREA A REALIZAR:", 0, 1)
            pdf.set_font(font_regular, "", 10)
            pdf.set_left_margin(10)
            pdf.multi_cell(190, 5, descripcion if descripcion else "No especificada")
            pdf.set_left_margin(10)

            pdf.ln(5)

            pdf.set_font(font_bold, "", 14)
            pdf.set_text_color(242, 190, 62)
            pdf.cell(120, 8, "IMPORTE TOTAL:")
            pdf.cell(0, 8, f"{float(importe):.2f} EUR", 0, 1, "R")

            pdf.set_text_color(0, 0, 0)
            pdf.ln(5)

            pdf.set_font(font_bold, "", 10)
            fecha_emisión = fecha_presupuesto.strftime("%d/%m/%Y")
            fecha_vencimiento = fecha_validez.strftime("%d/%m/%Y")
            
            pdf.cell(80, 6, f"Fecha del Presupuesto: {fecha_emisión}")
            pdf.cell(0, 6, f"Valido hasta: {fecha_vencimiento}", 0, 1)

            pdf.ln(5)

            pdf.set_font(font_regular, "I", 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, "Sistema de Gestion de Equipos Telereparo Vigo", 0, 1, "C")
            pdf.cell(0, 5, "Este presupuesto tiene validez de 15 dias naturales desde su fecha de emision", 0, 1, "C")

            carpeta_presupuestos = "presupuestos"
            if not os.path.exists(carpeta_presupuestos):
                os.makedirs(carpeta_presupuestos)

            cliente_limpio = cliente.replace("/", "-").replace("\\", "-") if cliente else "Cliente"
            equipo_limpio = equipo.replace("/", "-").replace("\\", "-") if equipo else "Equipo"
            
            nombre_archivo = f"{carpeta_presupuestos}/Presupuesto {cliente_limpio} {equipo_limpio}.pdf"
            pdf.output(nombre_archivo)

            messagebox.showinfo("Exito", f"Presupuesto exportado:\n{nombre_archivo}")

            import subprocess
            subprocess.Popen([nombre_archivo], shell=True)

            cursor.close()
            db.close()

        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar presupuesto: {e}")
            import traceback
            traceback.print_exc()

    def generar_factura(self, id_rep, id_presupuesto):
        try:
            db = conectar()
            cursor = db.cursor()

            if id_presupuesto and id_presupuesto > 0:
                cursor.execute("""
                    SELECT COALESCE(p.descripcion_trabajo, ''), 
                           COALESCE(p.importe_estimado, 0),
                           COALESCE(p.fecha_presupuesto, NOW()),
                           rd.id_cliente, c.nombre, c.telefono, c.email, c.direccion,
                           rd.nb_eqp, rd.marca_equipo, rd.modelo_equipo
                    FROM recepciones_despachos rd
                    LEFT JOIN clientes c ON rd.id_cliente = c.id_cli
                    LEFT JOIN presupuestos p ON rd.id_rep = p.id_rep AND p.id_presupuesto = %s
                    WHERE rd.id_rep = %s
                """, (id_presupuesto, id_rep))
                result = cursor.fetchone()
            else:
                result = None
            
            if not result:
                cursor.execute("""
                    SELECT '', 0, NOW(),
                           rd.id_cliente, c.nombre, c.telefono, c.email, c.direccion,
                           rd.nb_eqp, rd.marca_equipo, rd.modelo_equipo
                    FROM recepciones_despachos rd
                    LEFT JOIN clientes c ON rd.id_cliente = c.id_cli
                    WHERE rd.id_rep = %s
                """, (id_rep,))
                result = cursor.fetchone()
            
            if not result:
                messagebox.showerror("Error", "No se encontró información del ticket")
                cursor.close()
                db.close()
                return
            
            (descripcion_presupuesto, importe_presupuesto, fecha_presupuesto,
             id_cliente, cliente, telefono, email, direccion,
             equipo, marca, modelo) = result

            cursor.execute("""
                SELECT rep_rea, rep_time, imp_tarea, notas
                FROM reparaciones
                WHERE id_rep = %s
                ORDER BY fecha_creacion ASC
            """, (id_rep,))
            
            tareas = cursor.fetchall()
            
            cursor.close()
            db.close()

            try:
                from fpdf import FPDF
            except ImportError:
                messagebox.showerror("Error", "Se requiere fpdf2 para generar notas de entrega")
                return

            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.add_page()

            try:
                if LOGO_BASE64:
                    from PIL import Image
                    imagen_bytes = base64.b64decode(LOGO_BASE64)
                    imagen = Image.open(io.BytesIO(imagen_bytes)).convert("RGBA")
                    ancho, alto = imagen.size
                    pix = imagen.load()

                    muestras_borde = [
                        pix[0, 0],
                        pix[ancho - 1, 0],
                        pix[0, alto - 1],
                        pix[ancho - 1, alto - 1],
                        pix[ancho // 2, 0],
                        pix[ancho // 2, alto - 1],
                        pix[0, alto // 2],
                        pix[ancho - 1, alto // 2],
                    ]

                    color_fondo = muestras_borde[0] if muestras_borde else pix[0, 0]

                    def es_color_similar(color1, color2, tolerancia=30):
                        if len(color1) < 3 or len(color2) < 3:
                            return False
                        return all(abs(c1 - c2) <= tolerancia for c1, c2 in zip(color1[:3], color2[:3]))

                    for y in range(alto):
                        for x in range(ancho):
                            if es_color_similar(pix[x, y], color_fondo):
                                pix[x, y] = (*color_fondo[:3], 0) if len(color_fondo) >= 3 else (255, 255, 255, 0)

                    archivo_temp_logo = os.path.join(tempfile.gettempdir(), "logo_factura.png")
                    imagen.save(archivo_temp_logo, "PNG")
                    
                    ancho_logo = 40
                    pdf.image(archivo_temp_logo, x=160, y=8, w=ancho_logo)
            except Exception:
                pass

            font_regular, font_bold = self._configurar_fuentes_pdf(pdf)

            pdf.set_font(font_bold, "", 18)
            pdf.set_text_color(242, 190, 62)
            pdf.cell(0, 10, "NOTA DE ENTREGA", 0, 1, "C")
            pdf.set_font(font_regular, "", 8)
            pdf.cell(0, 3, "Informe de Reparacion", 0, 1, "C")

            pdf.set_font(font_regular, "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 5, f"Ticket: #{id_rep} | Nota: #{id_presupuesto}", 0, 1, "C")
            pdf.ln(5)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "CLIENTE:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, cliente if cliente else "No especificado", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "TELEFONO:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, telefono if telefono else "N/A", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "EMAIL:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, email if email else "N/A", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "DIRECCION:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, direccion if direccion else "N/A", 0, 1)

            pdf.ln(5)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "EQUIPO:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, equipo if equipo else "No especificado", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "MARCA:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, marca if marca else "N/A", 0, 1)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(50, 6, "MODELO:")
            pdf.set_font(font_regular, "", 10)
            pdf.cell(0, 6, modelo if modelo else "N/A", 0, 1)

            pdf.ln(5)

            pdf.set_font(font_bold, "", 11)
            pdf.cell(0, 6, "TRABAJOS REALIZADOS:", 0, 1)
            pdf.ln(2)

            pdf.set_font(font_regular, "", 9)
            total_factura = Decimal("0.00")
            
            pdf.set_text_color(242, 190, 62)
            pdf.set_font(font_bold, "", 9)
            pdf.cell(100, 6, "DESCRIPCION", 1, 0)
            pdf.cell(30, 6, "TIEMPO", 1, 0)
            pdf.cell(30, 6, "PRECIO (EUR)", 1, 1)
            pdf.set_text_color(0, 0, 0)

            pdf.set_font(font_regular, "", 9)
            for tarea in tareas:
                rep_rea, rep_time, imp_tarea, notas = tarea
                
                pdf.set_xy(10, pdf.get_y())
                pdf.multi_cell(100, 6, rep_rea if rep_rea else "-", 1, "L")
                
                alto_celda = pdf.get_y()
                pdf.set_xy(110, alto_celda - 6)
                pdf.cell(30, 6, str(rep_time) if rep_time else "-", 1, 0)
                
                precio_format = f"{float(imp_tarea):.2f}" if imp_tarea else "0.00"
                pdf.cell(30, 6, precio_format, 1, 1, "R")
                
                total_factura += Decimal(str(imp_tarea)) if imp_tarea else Decimal("0.00")

            pdf.ln(5)

            pdf.set_font(font_bold, "", 14)
            pdf.set_text_color(242, 190, 62)
            pdf.cell(130, 8, "COSTE TOTAL:")
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 8, f"{float(total_factura):.2f} EUR", 0, 1, "R")

            pdf.set_text_color(0, 0, 0)
            pdf.ln(5)

            pdf.set_font(font_regular, "", 10)
            fecha_emision = fecha_presupuesto.strftime("%d/%m/%Y") if fecha_presupuesto else "N/A"
            pdf.cell(80, 6, f"Fecha de emision: {fecha_emision}")
            pdf.cell(0, 6, f"Fecha de pago: {fecha_emision}", 0, 1)

            pdf.ln(5)

            pdf.set_font(font_regular, "I", 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, "Sistema de Gestion de Equipos Telereparo Vigo", 0, 1, "C")
            pdf.cell(0, 5, "Gracias por su confianza", 0, 1, "C")

            carpeta_notas = "notas_entrega"
            if not os.path.exists(carpeta_notas):
                os.makedirs(carpeta_notas)

            cliente_limpio = cliente.replace("/", "-").replace("\\", "-") if cliente else "Cliente"
            equipo_limpio = equipo.replace("/", "-").replace("\\", "-") if equipo else "Equipo"
            
            nombre_archivo = f"{carpeta_notas}/Nota de Entrega {cliente_limpio} {equipo_limpio}.pdf"
            pdf.output(nombre_archivo)

            messagebox.showinfo("Exito", f"Nota de entrega generada:\n{nombre_archivo}")

            import subprocess
            subprocess.Popen([nombre_archivo], shell=True)

        except Exception as e:
            messagebox.showerror("Error", f"Error al generar nota de entrega: {e}")
            import traceback
            traceback.print_exc()

    def generar_nota_manual(self):
        tabla = None
        if hasattr(self, 'tabla_ver') and self.tabla_ver:
            tabla = self.tabla_ver
        elif hasattr(self, 'tabla_registro') and self.tabla_registro:
            tabla = self.tabla_registro

        if not tabla:
            messagebox.showwarning("Error", "No se encontró tabla de registros")
            return

        seleccionado = tabla.selection()
        if not seleccionado:
            messagebox.showwarning("Advertencia", "Selecciona un registro primero")
            return

        item = seleccionado[0]
        valores = tabla.item(item, "values")
        id_rep = valores[0]
        
        try:
            db = conectar()
            cursor = db.cursor()

            cursor.execute("""
                SELECT id_presupuesto FROM presupuestos 
                WHERE id_rep = %s AND aceptado = TRUE 
                ORDER BY id_presupuesto DESC LIMIT 1
            """, (id_rep,))
            
            presupuesto = cursor.fetchone()
            
            if presupuesto:
                id_presupuesto = presupuesto[0]
            else:
                id_presupuesto = 0
            
            cursor.close()
            db.close()

            self.generar_factura(int(id_rep), int(id_presupuesto))

        except Exception as e:
            messagebox.showerror("Error", f"Error al generar nota de entrega: {e}")
            import traceback
            traceback.print_exc()

    def crear_vista_clientes(self):
        panel = self.crear_panel_base()

        ttk.Label(panel, text="Gestión de Clientes", style="Title.TLabel").pack(anchor="w", padx=8, pady=(4, 10))

        frame_form = ttk.LabelFrame(panel, text=" Nuevo Cliente ", padding=10)
        frame_form.pack(fill="x", padx=8, pady=8)

        ttk.Label(frame_form, text="Nombre:", style="Field.TLabel").grid(row=0, column=0, sticky="w", padx=5)
        self.txt_cli_nombre = ttk.Entry(frame_form, width=40)
        self.txt_cli_nombre.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame_form, text="Teléfono:", style="Field.TLabel").grid(row=0, column=2, sticky="w", padx=5)
        self.txt_cli_telefono = ttk.Entry(frame_form, width=20)
        self.txt_cli_telefono.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(frame_form, text="Email:", style="Field.TLabel").grid(row=1, column=0, sticky="w", padx=5)
        self.txt_cli_email = ttk.Entry(frame_form, width=40)
        self.txt_cli_email.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame_form, text="Ciudad:", style="Field.TLabel").grid(row=1, column=2, sticky="w", padx=5)
        self.txt_cli_ciudad = ttk.Entry(frame_form, width=20)
        self.txt_cli_ciudad.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(frame_form, text="Dirección:", style="Field.TLabel").grid(row=2, column=0, sticky="w", padx=5)
        self.txt_cli_direccion = ttk.Entry(frame_form, width=40)
        self.txt_cli_direccion.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(frame_form, text="Código Postal:", style="Field.TLabel").grid(row=2, column=2, sticky="w", padx=5)
        self.txt_cli_cp = ttk.Entry(frame_form, width=15)
        self.txt_cli_cp.grid(row=2, column=3, padx=5, pady=5)

        ttk.Label(frame_form, text="Notas:", style="Field.TLabel").grid(row=3, column=0, sticky="nw", padx=5)
        self.txt_cli_notas = self.crear_text_field(frame_form, height=3, width=80)
        self.txt_cli_notas.grid(row=3, column=1, columnspan=3, padx=5, pady=5)

        btn_frame = ttk.Frame(panel, style="Card.TFrame")
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Button(btn_frame, text="Guardar Cliente", command=self.guardar_cliente).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Editar Seleccionado", command=self.editar_cliente_seleccionado).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Eliminar Seleccionado", command=self.eliminar_cliente_seleccionado).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Refrescar", command=self.cargar_clientes).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Volver al menú", command=lambda: self.mostrar_vista("menu")).pack(side="right", padx=5)

        frame_tabla = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 8))
        frame_tabla.pack(fill="both", expand=True)

        self.tabla_clientes = ttk.Treeview(
            frame_tabla,
            columns=("id", "nombre", "telefono", "email", "ciudad"),
            show="headings",
            height=15
        )
        self.tabla_clientes.heading("id", text="ID")
        self.tabla_clientes.heading("nombre", text="NOMBRE")
        self.tabla_clientes.heading("telefono", text="TELÉFONO")
        self.tabla_clientes.heading("email", text="EMAIL")
        self.tabla_clientes.heading("ciudad", text="CIUDAD")

        self.tabla_clientes.column("id", width=50, anchor="center")
        self.tabla_clientes.column("nombre", width=250)
        self.tabla_clientes.column("telefono", width=120)
        self.tabla_clientes.column("email", width=200)
        self.tabla_clientes.column("ciudad", width=150)

        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tabla_clientes.yview)
        self.tabla_clientes.configure(yscrollcommand=scrollbar.set)
        self.tabla_clientes.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tabla_clientes.bind("<Double-1>", lambda e: self.editar_cliente_seleccionado())

        self.frames["clientes"] = panel

    def crear_vista_estadisticas(self):
        panel = self.crear_panel_base()

        ttk.Label(panel, text="Estadísticas", style="Title.TLabel").pack(anchor="w", padx=8, pady=(4, 10))

        frame_filtros = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 10))
        frame_filtros.pack(fill="x", padx=8, pady=8)

        ttk.Label(frame_filtros, text="Período:", style="Field.TLabel").pack(side="left", padx=5)
        self.combo_periodo = ttk.Combobox(frame_filtros, state="readonly", width=20,
                                         values=["Todos", "Este mes", "Mes actual", "Este año", "Último trimestre"])
        self.combo_periodo.pack(side="left", padx=5)
        self.combo_periodo.current(0)

        ttk.Button(frame_filtros, text="Actualizar", command=self.recargar_estadisticas).pack(side="left", padx=5)
        ttk.Button(frame_filtros, text="Volver al menú", command=lambda: self.mostrar_vista("menu")).pack(side="right", padx=5)

        frame_stats = ttk.Frame(panel, style="Card.TFrame", padding=10)
        frame_stats.pack(fill="both", expand=True, padx=8, pady=8)

        self.lbl_total_reparaciones = ttk.Label(frame_stats, text="Total Reparaciones: 0", style="Title.TLabel")
        self.lbl_total_reparaciones.pack(anchor="w", pady=5)

        self.lbl_ingresos_totales = ttk.Label(frame_stats, text="Ingresos Totales: € 0.00", style="Title.TLabel", foreground=self.colores_ui["fg_value"])
        self.lbl_ingresos_totales.pack(anchor="w", pady=5)

        self.lbl_precio_promedio = ttk.Label(frame_stats, text="Precio Promedio: € 0.00", style="Subtitle.TLabel")
        self.lbl_precio_promedio.pack(anchor="w", pady=5)

        self.lbl_equipos_reparados = ttk.Label(frame_stats, text="Equipos Únicos: 0", style="Subtitle.TLabel")
        self.lbl_equipos_reparados.pack(anchor="w", pady=5)

        self.lbl_clientes_totales = ttk.Label(frame_stats, text="Clientes Totales: 0", style="Subtitle.TLabel")
        self.lbl_clientes_totales.pack(anchor="w", pady=5)

        ttk.Separator(frame_stats, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(frame_stats, text="Equipos más reparados:", style="Subtitle.TLabel").pack(anchor="w", pady=(10, 5))

        self.txt_stats_equipos = self.crear_text_field(frame_stats, height=5, width=80)
        self.txt_stats_equipos.pack(fill="x", pady=5)

        ttk.Label(frame_stats, text="Clientes más frecuentes:", style="Subtitle.TLabel").pack(anchor="w", pady=(10, 5))

        self.txt_stats_clientes = self.crear_text_field(frame_stats, height=5, width=80)
        self.txt_stats_clientes.pack(fill="x", pady=5)

        self.frames["estadisticas"] = panel

    def crear_vista_respaldo(self):
        panel = self.crear_panel_base()

        ttk.Label(panel, text="Respaldo de Base de Datos", style="Title.TLabel").pack(anchor="w", padx=8, pady=(4, 10))

        frame_opciones = ttk.LabelFrame(panel, text=" Opciones de Respaldo ", padding=10)
        frame_opciones.pack(fill="x", padx=8, pady=8)

        ttk.Label(frame_opciones, text="Ruta de destino:", style="Field.TLabel").pack(side="left", padx=5)
        self.txt_ruta_respaldo = ttk.Entry(frame_opciones, width=60)
        self.txt_ruta_respaldo.pack(side="left", padx=5)
        self.txt_ruta_respaldo.insert(0, os.path.expanduser("~/Desktop"))

        ttk.Button(frame_opciones, text="Seleccionar ruta", command=self.seleccionar_ruta_respaldo).pack(side="left", padx=5)

        btn_frame = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 8))
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Button(btn_frame, text="Crear Respaldo Ahora", command=self.crear_respaldo_manual).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Ver Historial de Respaldos", command=self.ver_historial_respaldos).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Volver al menú", command=lambda: self.mostrar_vista("menu")).pack(side="right", padx=5)

        frame_log = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 8))
        frame_log.pack(fill="both", expand=True, padx=8, pady=8)

        self.txt_log_respaldo = self.crear_text_field(frame_log, height=10, width=100)
        self.txt_log_respaldo.config(font=("Consolas", 9), wrap="word")
        self.txt_log_respaldo.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=self.txt_log_respaldo.yview)
        self.txt_log_respaldo.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.frames["respaldo"] = panel

    def crear_vista_conexion(self):
        panel = self.crear_panel_base()

        ttk.Label(panel, text="Comprobar conexión a la base de datos", style="Title.TLabel").pack(anchor="w", padx=8, pady=(4, 10))

        barra = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 8))
        barra.pack(fill="x")

        ttk.Button(barra, text="Ejecutar comprobación", command=self.comprobar_conexion).pack(side="left", padx=5)
        ttk.Button(barra, text="Volver al menú principal", command=lambda: self.mostrar_vista("menu")).pack(side="right", padx=5)

        frame_log = ttk.Frame(panel, style="Card.TFrame", padding=(8, 0, 8, 8))
        frame_log.pack(fill="both", expand=True)

        self.txt_log = self.crear_text_field(frame_log, height=10, width=100)
        self.txt_log.config(font=("Consolas", 10), wrap="word", insertbackground=self.colores_ui["fg_text"])
        self.txt_log.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.frames["conexion"] = panel

    def limpiar_campos_registro(self):
        self.txt_eqp.delete(0, "end")
        self.txt_marca.delete(0, "end")
        self.txt_modelo.delete(0, "end")
        self.combo_categoria.set("")
        self.txt_diagnostico.delete("1.0", "end")
        self.txt_garantia.delete(0, "end")
        self.txt_garantia.insert(0, "30")
        self.combo_cliente_nuevo.set("")

    def registrar_equipo(self):
        cliente_id = self.obtener_id_cliente(self.combo_cliente_nuevo.get())
        equipo = self.txt_eqp.get().strip()
        marca = self.txt_marca.get().strip()
        modelo = self.txt_modelo.get().strip()
        categoria = self.combo_categoria.get()
        diagnostico = self.txt_diagnostico.get("1.0", "end").strip()
        garantia = self.txt_garantia.get().strip()

        if not cliente_id or not equipo:
            messagebox.showwarning("SGETV", "Completa cliente y equipo")
            return

        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            fecha = datetime.now().date()
            garantia_dias = int(garantia) if garantia else 30
            fecha_garantia = fecha + timedelta(days=garantia_dias)

            sql = """INSERT INTO recepciones_despachos 
                     (f_entr, nb_eqp, id_cliente, marca_equipo, modelo_equipo, 
                      categoria_equipo, estado_id, diagnostico, garantia_dias, fecha_vencimiento_garantia) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, (fecha, equipo, cliente_id, marca, modelo, categoria, 1, diagnostico or None, garantia_dias, fecha_garantia))
            db.commit()

            self.registrar_auditoria(db, "recepciones_despachos", None, "INSERT", None, 
                                    {"equipo": equipo, "cliente": cliente_id})

            self.limpiar_campos_registro()
            self.actualizar_tabla_registro()
            messagebox.showinfo("SGETV", "Equipo registrado correctamente")
        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al registrar: {e}")
        finally:
            if db:
                db.close()

    def editar_equipo_seleccionado(self):
        item = self.tabla_registro.selection()
        if not item:
            messagebox.showwarning("SGETV", "Selecciona un equipo para editar")
            return

        id_equipo = self.tabla_registro.item(item)["values"][0]
        self.mostrar_dialogo_editar_equipo(id_equipo)

    def mostrar_dialogo_editar_equipo(self, id_equipo):
        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute("""SELECT nb_eqp, marca_equipo, modelo_equipo, categoria_equipo, 
                                     estado_id, diagnostico, garantia_dias 
                             FROM recepciones_despachos WHERE id_rep = %s""", (id_equipo,))
            equipo_data = cursor.fetchone()
            db.close()

            if not equipo_data:
                messagebox.showerror("SGETV", "Equipo no encontrado")
                return

            dlg = tk.Toplevel(self.root)
            dlg.title(f"Editar Equipo #{id_equipo}")
            dlg.geometry("600x400")
            dlg.grab_set()
            dlg.attributes('-topmost', True)
            dlg.lift()
            dlg.focus()

            frame = ttk.Frame(dlg, padding=10)
            frame.pack(fill="both", expand=True)

            ttk.Label(frame, text="Equipo:").grid(row=0, column=0, sticky="w", pady=5)
            txt_eq = ttk.Entry(frame, width=40)
            txt_eq.grid(row=0, column=1, pady=5, padx=10)
            txt_eq.insert(0, equipo_data[0] or "")

            ttk.Label(frame, text="Marca:").grid(row=1, column=0, sticky="w", pady=5)
            txt_mar = ttk.Entry(frame, width=40)
            txt_mar.grid(row=1, column=1, pady=5, padx=10)
            txt_mar.insert(0, equipo_data[1] or "")

            ttk.Label(frame, text="Modelo:").grid(row=2, column=0, sticky="w", pady=5)
            txt_mod = ttk.Entry(frame, width=40)
            txt_mod.grid(row=2, column=1, pady=5, padx=10)
            txt_mod.insert(0, equipo_data[2] or "")

            ttk.Label(frame, text="Categoría:").grid(row=3, column=0, sticky="w", pady=5)
            combo_cat = ttk.Combobox(frame, width=37, state="readonly",
                                     values=["Móvil", "Tablet", "Laptop", "PC", "Periférico", "Otro"])
            combo_cat.grid(row=3, column=1, pady=5, padx=10)
            combo_cat.set(equipo_data[3] or "")

            ttk.Label(frame, text="Estado:").grid(row=4, column=0, sticky="w", pady=5)
            combo_est = ttk.Combobox(frame, width=37, state="readonly",
                                     values=["Pendiente", "En progreso", "Pausada", "Completada", "Entregada", "Rechazada"])
            combo_est.grid(row=4, column=1, pady=5, padx=10)
            db = conectar()
            cursor = db.cursor()
            cursor.execute("SELECT nombre FROM estados_reparacion WHERE id_estado = %s", (equipo_data[4],))
            estado_nombre = cursor.fetchone()
            db.close()
            if estado_nombre:
                combo_est.set(estado_nombre[0])

            ttk.Label(frame, text="Diagnóstico:").grid(row=5, column=0, sticky="nw", pady=5)
            txt_diag = self.crear_text_field(frame, height=4, width=40)
            txt_diag.grid(row=5, column=1, pady=5, padx=10)
            txt_diag.insert("1.0", equipo_data[5] or "")

            ttk.Label(frame, text="Garantía (días):").grid(row=6, column=0, sticky="w", pady=5)
            txt_gar = ttk.Entry(frame, width=10)
            txt_gar.grid(row=6, column=1, sticky="w", pady=5, padx=10)
            txt_gar.insert(0, str(equipo_data[6] or 30))

            def guardar_cambios():
                db = None
                try:
                    db = conectar()
                    cursor = db.cursor()
                    estado_nombre = combo_est.get()
                    cursor.execute("SELECT id_estado FROM estados_reparacion WHERE nombre = %s", (estado_nombre,))
                    estado_result = cursor.fetchone()
                    estado_id = estado_result[0] if estado_result else 1

                    sql = """UPDATE recepciones_despachos 
                             SET nb_eqp = %s, marca_equipo = %s, modelo_equipo = %s, 
                                 categoria_equipo = %s, estado_id = %s, diagnostico = %s, garantia_dias = %s
                             WHERE id_rep = %s"""
                    cursor.execute(sql, (txt_eq.get(), txt_mar.get(), txt_mod.get(), combo_cat.get(), 
                                        estado_id, txt_diag.get("1.0", "end"), int(txt_gar.get() or 30), id_equipo))
                    db.commit()

                    self.registrar_auditoria(db, "recepciones_despachos", id_equipo, "UPDATE", 
                                            equipo_data, {"equipo": txt_eq.get(), "marca": txt_mar.get()})

                    messagebox.showinfo("SGETV", "Equipo actualizado correctamente")
                    dlg.destroy()
                    self.actualizar_tabla_registro()
                except mysql.connector.Error as e:
                    messagebox.showerror("SGETV", f"Error al actualizar: {e}")
                finally:
                    if db:
                        db.close()

            ttk.Button(frame, text="Guardar cambios", command=guardar_cambios).grid(row=7, column=0, columnspan=2, pady=20)

        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al cargar datos: {e}")

    def cargar_combo_clientes(self, combo):
        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute("SELECT nombre FROM clientes ORDER BY nombre")
            clientes = [row[0] for row in cursor.fetchall()]
            combo['values'] = clientes
        except mysql.connector.Error:
            pass
        finally:
            if db:
                db.close()

    def obtener_id_cliente(self, nombre):
        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute("SELECT id_cli FROM clientes WHERE nombre = %s", (nombre,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else None
        except mysql.connector.Error:
            return None
        finally:
            if db:
                db.close()

    def eliminar_registro(self):
        item = self.tabla_registro.selection()
        if not item:
            messagebox.showwarning("SGETV", "Selecciona un equipo para eliminar")
            return

        if not messagebox.askyesno("Confirmar", "¿Eliminar este equipo? No se puede deshacer"):
            return

        id_equipo = self.tabla_registro.item(item)["values"][0]
        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute("DELETE FROM recepciones_despachos WHERE id_rep = %s", (id_equipo,))
            db.commit()
            self.registrar_auditoria(db, "recepciones_despachos", id_equipo, "DELETE", None, None)
            self.actualizar_tabla_registro()
            messagebox.showinfo("SGETV", "Equipo eliminado correctamente")
        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al eliminar: {e}")
        finally:
            if db:
                db.close()

    def actualizar_tabla_registro(self):
        for item in self.tabla_registro.get_children():
            self.tabla_registro.delete(item)

        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute("""SELECT rd.id_rep, rd.f_entr, rd.nb_eqp, rd.marca_equipo, rd.modelo_equipo, 
                                     c.nombre, rd.categoria_equipo, er.nombre, rd.f_sal
                             FROM recepciones_despachos rd
                             LEFT JOIN clientes c ON rd.id_cliente = c.id_cli
                             LEFT JOIN estados_reparacion er ON rd.estado_id = er.id_estado
                             ORDER BY rd.id_rep DESC""")
            for id_rep, fecha, equipo, marca, modelo, cliente, categoria, estado, f_sal in cursor.fetchall():
                self.tabla_registro.insert(
                    "",
                    "end",
                    values=(id_rep, self.formatear_fecha(fecha), equipo, marca or "-", modelo or "-",
                            cliente or "-", categoria or "-", estado or "Pendiente", 
                            self.formatear_fecha(f_sal) if f_sal else "-"),
                )
        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al cargar registros: {e}")
        finally:
            if db:
                db.close()

    def cargar_registros_filtrados(self):
        for item in self.tabla_ver.get_children():
            self.tabla_ver.delete(item)

        db = None
        try:
            db = conectar()
            cursor = db.cursor()

            sql = """SELECT rd.id_rep, rd.f_entr, rd.nb_eqp, rd.marca_equipo, rd.modelo_equipo, 
                            c.nombre, rd.categoria_equipo, er.nombre, rd.f_sal, rd.total
                     FROM recepciones_despachos rd
                     LEFT JOIN clientes c ON rd.id_cliente = c.id_cli
                     LEFT JOIN estados_reparacion er ON rd.estado_id = er.id_estado
                     WHERE 1=1"""

            params = []

            if self.filtro_ticket.get().strip():
                sql += " AND rd.id_rep = %s"
                params.append(int(self.filtro_ticket.get().strip()))

            if self.filtro_equipo.get().strip():
                sql += " AND rd.nb_eqp LIKE %s"
                params.append(f"%{self.filtro_equipo.get().strip()}%")

            if self.filtro_cliente.get().strip():
                sql += " AND c.nombre LIKE %s"
                params.append(f"%{self.filtro_cliente.get().strip()}%")

            if self.filtro_marca.get().strip():
                sql += " AND (rd.marca_equipo LIKE %s OR rd.modelo_equipo LIKE %s)"
                marca_filtro = f"%{self.filtro_marca.get().strip()}%"
                params.extend([marca_filtro, marca_filtro])

            fecha_desde = self.filtro_fecha_desde.get_date()
            fecha_hasta = self.filtro_fecha_hasta.get_date()
            if fecha_desde:
                sql += " AND rd.f_entr >= %s"
                params.append(fecha_desde)
            if fecha_hasta:
                sql += " AND rd.f_entr <= %s"
                params.append(fecha_hasta)

            if self.filtro_precio_desde.get().strip():
                sql += " AND rd.total >= %s"
                params.append(float(self.filtro_precio_desde.get().strip()))

            if self.filtro_precio_hasta.get().strip():
                sql += " AND rd.total <= %s"
                params.append(float(self.filtro_precio_hasta.get().strip()))

            if self.filtro_estado.get():
                sql += " AND er.nombre = %s"
                params.append(self.filtro_estado.get())

            if self.filtro_categoria.get():
                sql += " AND rd.categoria_equipo = %s"
                params.append(self.filtro_categoria.get())

            sql += " ORDER BY rd.id_rep DESC"

            cursor.execute(sql, params)
            self.filas_ver = []
            for id_rep, fecha, equipo, marca, modelo, cliente, categoria, estado, f_sal, total in cursor.fetchall():
                self.filas_ver.append((id_rep, fecha, equipo, cliente, f_sal, total))
                self.tabla_ver.insert(
                    "",
                    "end",
                    values=(id_rep, self.formatear_fecha(fecha), equipo, marca or "-", modelo or "-",
                            cliente or "-", categoria or "-", estado or "Pendiente",
                            self.formatear_fecha(f_sal) if f_sal else "-", self.formatear_importe(total) if total else "-"),
                )

            self.lbl_total.config(text=f"Total de registros: {len(self.filas_ver)}")
        except (mysql.connector.Error, ValueError) as e:
            messagebox.showerror("SGETV", f"Error al cargar registros: {e}")
        finally:
            if db:
                db.close()

    def limpiar_filtros(self):
        self.filtro_ticket.delete(0, "end")
        self.filtro_equipo.delete(0, "end")
        self.filtro_cliente.delete(0, "end")
        self.filtro_marca.delete(0, "end")
        self.filtro_estado.set("")
        self.filtro_categoria.set("")
        self.filtro_precio_desde.delete(0, "end")
        self.filtro_precio_hasta.delete(0, "end")
        self.cargar_registros_filtrados()

    def exportar_csv(self):
        if not self.filas_ver:
            messagebox.showwarning("SGETV", "No hay registros para exportar")
            return

        ruta = filedialog.asksaveasfilename(
            title="Guardar CSV",
            defaultextension=".csv",
            filetypes=[("Archivo CSV", "*.csv")],
            initialfile="registros_telereparo.csv",
        )

        if not ruta:
            return

        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:
                writer = csv.writer(archivo)
                writer.writerow(["ID", "Fecha Entrada", "Equipo", "Cliente", "Fecha Salida", "Total (€)"])
                for id_rep, fecha, equipo, cliente, f_sal, total in self.filas_ver:
                    writer.writerow([
                        id_rep,
                        self.formatear_fecha(fecha),
                        equipo,
                        cliente or "-",
                        self.formatear_fecha(f_sal) if f_sal else "-",
                        self.formatear_importe(total) if total else "-"
                    ])
            messagebox.showinfo("SGETV", f"CSV guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("SGETV", f"Error al guardar CSV: {e}")

    def exportar_pdf(self):
        if not HAS_REPORTLAB:
            messagebox.showerror("SGETV", "Se requiere instalar 'reportlab' para exportar a PDF\nPip install reportlab")
            return

        if not self.filas_ver:
            messagebox.showwarning("SGETV", "No hay registros para exportar")
            return

        ruta = filedialog.asksaveasfilename(
            title="Guardar PDF",
            defaultextension=".pdf",
            filetypes=[("Archivo PDF", "*.pdf")],
            initialfile="registros_telereparo.pdf",
        )

        if not ruta:
            return

        try:
            doc = SimpleDocTemplate(ruta, pagesize=A4)
            elements = []

            styles = getSampleStyleSheet()
            paleta = self.colores_ui
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor(paleta["fg_title"]),
                spaceAfter=30,
            )
            elements.append(Paragraph("Registros de Reparación", title_style))
            elements.append(Spacer(1, 0.2 * inch))

            data = [["ID", "Fecha", "Equipo", "Cliente", "Salida", "Total"]]
            for id_rep, fecha, equipo, cliente, f_sal, total in self.filas_ver:
                data.append([
                    str(id_rep),
                    self.formatear_fecha(fecha),
                    equipo[:30],
                    cliente or "-",
                    self.formatear_fecha(f_sal) if f_sal else "-",
                    f"€ {self.formatear_importe(total)}"
                ])

            table = Table(data, colWidths=[0.8*inch, 0.9*inch, 2*inch, 1.5*inch, 0.9*inch, 0.8*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(paleta["bg_table_header"])),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(paleta["fg_title"])),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor(paleta["bg_table"])),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor(paleta["fg_text"])),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor(paleta["bg_table"]), colors.HexColor(paleta["bg_table_alt"])]),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor(paleta["grid"])),
            ]))

            elements.append(table)
            doc.build(elements)
            messagebox.showinfo("SGETV", f"PDF guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("SGETV", f"Error al guardar PDF: {e}")

    def guardar_cliente(self):
        nombre = self.txt_cli_nombre.get().strip()
        telefono = self.txt_cli_telefono.get().strip()
        email = self.txt_cli_email.get().strip()
        ciudad = self.txt_cli_ciudad.get().strip()
        direccion = self.txt_cli_direccion.get().strip()
        cp = self.txt_cli_cp.get().strip()
        notas = self.txt_cli_notas.get("1.0", "end").strip()

        if not nombre:
            messagebox.showwarning("SGETV", "El nombre es obligatorio")
            return

        db = None
        try:
            db = conectar()
            cursor = db.cursor()

            sql = """INSERT INTO clientes (nombre, telefono, email, direccion, ciudad, cp, notas)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, (nombre, telefono or None, email or None, direccion or None, ciudad or None, cp or None, notas or None))
            db.commit()

            self.registrar_auditoria(db, "clientes", None, "INSERT", None, {"nombre": nombre})

            self.limpiar_campos_cliente()
            self.cargar_clientes()
            self.cargar_combo_clientes(self.combo_cliente_nuevo)
            messagebox.showinfo("SGETV", "Cliente guardado correctamente")
        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al guardar cliente: {e}")
        finally:
            if db:
                db.close()

    def limpiar_campos_cliente(self):
        self.txt_cli_nombre.delete(0, "end")
        self.txt_cli_telefono.delete(0, "end")
        self.txt_cli_email.delete(0, "end")
        self.txt_cli_ciudad.delete(0, "end")
        self.txt_cli_direccion.delete(0, "end")
        self.txt_cli_cp.delete(0, "end")
        self.txt_cli_notas.delete("1.0", "end")

    def cargar_clientes(self):
        for item in self.tabla_clientes.get_children():
            self.tabla_clientes.delete(item)

        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute("SELECT id_cli, nombre, telefono, email, ciudad FROM clientes ORDER BY nombre")
            for id_cli, nombre, telefono, email, ciudad in cursor.fetchall():
                self.tabla_clientes.insert("", "end", values=(id_cli, nombre, telefono or "-", email or "-", ciudad or "-"))
        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al cargar clientes: {e}")
        finally:
            if db:
                db.close()

    def editar_cliente_seleccionado(self):
        item = self.tabla_clientes.selection()
        if not item:
            messagebox.showwarning("SGETV", "Selecciona un cliente para editar")
            return

        id_cliente = self.tabla_clientes.item(item)["values"][0]
        self.mostrar_dialogo_editar_cliente(id_cliente)

    def mostrar_dialogo_editar_cliente(self, id_cliente):
        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute("SELECT nombre, telefono, email, direccion, ciudad, cp, notas FROM clientes WHERE id_cli = %s", (id_cliente,))
            datos = cursor.fetchone()
            db.close()

            if not datos:
                messagebox.showerror("SGETV", "Cliente no encontrado")
                return

            dlg = tk.Toplevel(self.root)
            dlg.title(f"Editar Cliente #{id_cliente}")
            dlg.geometry("600x450")
            dlg.grab_set()
            dlg.attributes('-topmost', True)
            dlg.lift()
            dlg.focus()

            frame = ttk.Frame(dlg, padding=10)
            frame.pack(fill="both", expand=True)

            ttk.Label(frame, text="Nombre:").grid(row=0, column=0, sticky="w", pady=5)
            txt_nom = ttk.Entry(frame, width=40)
            txt_nom.grid(row=0, column=1, pady=5, padx=10)
            txt_nom.insert(0, datos[0] or "")

            ttk.Label(frame, text="Teléfono:").grid(row=1, column=0, sticky="w", pady=5)
            txt_tel = ttk.Entry(frame, width=40)
            txt_tel.grid(row=1, column=1, pady=5, padx=10)
            txt_tel.insert(0, datos[1] or "")

            ttk.Label(frame, text="Email:").grid(row=2, column=0, sticky="w", pady=5)
            txt_email = ttk.Entry(frame, width=40)
            txt_email.grid(row=2, column=1, pady=5, padx=10)
            txt_email.insert(0, datos[2] or "")

            ttk.Label(frame, text="Dirección:").grid(row=3, column=0, sticky="w", pady=5)
            txt_dir = ttk.Entry(frame, width=40)
            txt_dir.grid(row=3, column=1, pady=5, padx=10)
            txt_dir.insert(0, datos[3] or "")

            ttk.Label(frame, text="Ciudad:").grid(row=4, column=0, sticky="w", pady=5)
            txt_ciu = ttk.Entry(frame, width=40)
            txt_ciu.grid(row=4, column=1, pady=5, padx=10)
            txt_ciu.insert(0, datos[4] or "")

            ttk.Label(frame, text="Código Postal:").grid(row=5, column=0, sticky="w", pady=5)
            txt_cp = ttk.Entry(frame, width=15)
            txt_cp.grid(row=5, column=1, sticky="w", pady=5, padx=10)
            txt_cp.insert(0, datos[5] or "")

            ttk.Label(frame, text="Notas:").grid(row=6, column=0, sticky="nw", pady=5)
            txt_notas = self.crear_text_field(frame, height=4, width=40)
            txt_notas.grid(row=6, column=1, pady=5, padx=10)
            txt_notas.insert("1.0", datos[6] or "")

            def guardar_cambios():
                db = None
                try:
                    db = conectar()
                    cursor = db.cursor()
                    sql = """UPDATE clientes 
                             SET nombre = %s, telefono = %s, email = %s, direccion = %s, ciudad = %s, cp = %s, notas = %s
                             WHERE id_cli = %s"""
                    cursor.execute(sql, (txt_nom.get(), txt_tel.get() or None, txt_email.get() or None,
                                        txt_dir.get() or None, txt_ciu.get() or None, txt_cp.get() or None,
                                        txt_notas.get("1.0", "end") or None, id_cliente))
                    db.commit()

                    self.registrar_auditoria(db, "clientes", id_cliente, "UPDATE", datos, {"nombre": txt_nom.get()})

                    messagebox.showinfo("SGETV", "Cliente actualizado correctamente")
                    dlg.destroy()
                    self.cargar_clientes()
                    self.cargar_combo_clientes(self.combo_cliente_nuevo)
                except mysql.connector.Error as e:
                    messagebox.showerror("SGETV", f"Error al actualizar: {e}")
                finally:
                    if db:
                        db.close()

            ttk.Button(frame, text="Guardar cambios", command=guardar_cambios).grid(row=7, column=0, columnspan=2, pady=20)

        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al cargar datos: {e}")

    def eliminar_cliente_seleccionado(self):
        item = self.tabla_clientes.selection()
        if not item:
            messagebox.showwarning("SGETV", "Selecciona un cliente para eliminar")
            return

        id_cliente = self.tabla_clientes.item(item)["values"][0]

        if not messagebox.askyesno("Confirmar", "¿Eliminar este cliente? No se puede deshacer"):
            return

        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute("DELETE FROM clientes WHERE id_cli = %s", (id_cliente,))
            db.commit()

            self.registrar_auditoria(db, "clientes", id_cliente, "DELETE", None, None)

            self.cargar_clientes()
            self.cargar_combo_clientes(self.combo_cliente_nuevo)
            messagebox.showinfo("SGETV", "Cliente eliminado correctamente")
        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al eliminar cliente: {e}")
        finally:
            if db:
                db.close()

    def crear_vista_tareas(self):
        pass

    def abrir_editar_tareas(self, event):
        item = self.tabla_registro.selection()
        if not item:
            messagebox.showwarning("SGETV", "Selecciona un equipo")
            return

        id_equipo = self.tabla_registro.item(item)["values"][0]
        equipo_nombre = self.tabla_registro.item(item)["values"][2]

        self.id_equipo_tareas = id_equipo
        self.eq_nombre_tareas = equipo_nombre

        self.crear_ventana_tareas(id_equipo, equipo_nombre)

    def crear_ventana_tareas(self, id_equipo, equipo_nombre):
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Gestión de Tareas - {equipo_nombre} (Ticket #{id_equipo})")
        ventana.geometry("1000x700")
        ventana.grab_set()
        ventana.attributes('-topmost', True)
        ventana.lift()
        ventana.focus()

        container = ttk.Frame(ventana, padding=10)
        container.pack(fill="both", expand=True)

        lbl_titulo = ttk.Label(container, text=f"Gestionar tareas - {equipo_nombre}", style="Title.TLabel")
        lbl_titulo.pack(anchor="w", pady=(0, 10))

        frame_form = ttk.LabelFrame(container, text=" Nueva Tarea ", padding=10)
        frame_form.pack(fill="x", pady=(0, 10))

        ttk.Label(frame_form, text="Descripción:").grid(row=0, column=0, sticky="nw", padx=5)
        txt_desc = self.crear_text_field(frame_form, height=3, width=70)
        txt_desc.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame_form, text="Tiempo:").grid(row=1, column=0, sticky="w", padx=5)
        txt_tiempo = ttk.Entry(frame_form, width=40)
        txt_tiempo.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frame_form, text="Precio (€):").grid(row=2, column=0, sticky="w", padx=5)
        txt_precio = ttk.Entry(frame_form, width=20)
        txt_precio.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frame_form, text="Piezas utilizadas:").grid(row=3, column=0, sticky="nw", padx=5)
        txt_piezas = self.crear_text_field(frame_form, height=3, width=70)
        txt_piezas.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(frame_form, text="Notas:").grid(row=4, column=0, sticky="nw", padx=5)
        txt_notas = self.crear_text_field(frame_form, height=2, width=70)
        txt_notas.grid(row=4, column=1, padx=5, pady=5)

        frame_total = ttk.LabelFrame(container, text=" Importe Total ", padding=10)
        frame_total.pack(fill="x", pady=(0, 10))
        lbl_total = ttk.Label(frame_total, text="€ 0.00", style="Title.TLabel", foreground=self.colores_ui["fg_value"])
        lbl_total.pack(anchor="e", padx=5)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(0, 10))

        def guardar_tarea():
            descripcion = txt_desc.get("1.0", "end").strip()
            tiempo = txt_tiempo.get().strip()
            precio_texto = txt_precio.get().strip()
            piezas = txt_piezas.get("1.0", "end").strip()
            notas = txt_notas.get("1.0", "end").strip()

            if not descripcion:
                messagebox.showwarning("SGETV", "Describe la tarea realizada")
                return

            precio = Decimal("0.00")
            if precio_texto:
                try:
                    precio = Decimal(precio_texto.replace(",", ".")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                except InvalidOperation:
                    messagebox.showwarning("SGETV", "Precio inválido")
                    return

            db = None
            try:
                db = conectar()
                cursor = db.cursor()

                cursor.execute("SELECT c.nombre FROM recepciones_despachos rd LEFT JOIN clientes c ON rd.id_cliente = c.id_cli WHERE rd.id_rep = %s", (id_equipo,))
                cliente_result = cursor.fetchone()
                cliente = cliente_result[0] if cliente_result and cliente_result[0] else "Sin asignar"

                sql = "INSERT INTO reparaciones (id_rep, n_cli, rep_rea, rep_time, imp_tarea, estado_id, notas, fecha_creacion) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (id_equipo, cliente, descripcion, tiempo or None, float(precio), 2, notas or None, datetime.now()))
                db.commit()

                self.registrar_auditoria(db, "reparaciones", None, "INSERT", None, {"descripcion": descripcion[:50]})

                if piezas:
                    for linea in piezas.split('\n'):
                        linea = linea.strip()
                        if linea:
                            try:
                                partes = linea.split('|')
                                if len(partes) >= 2:
                                    nombre_pieza = partes[0].strip()
                                    cantidad = Decimal(partes[1].strip() if len(partes) > 1 else "1")
                                    precio_pieza = Decimal(partes[2].strip() if len(partes) > 2 else "0")
                                    subtotal = cantidad * precio_pieza

                                    cursor.execute("""INSERT INTO piezas_utilizadas (id_rep, nombre_pieza, cantidad, precio_unitario, subtotal)
                                                     VALUES (%s, %s, %s, %s, %s)""",
                                                 (id_equipo, nombre_pieza, float(cantidad), float(precio_pieza), float(subtotal)))
                            except Exception:
                                pass
                    db.commit()

                txt_desc.delete("1.0", "end")
                txt_tiempo.delete(0, "end")
                txt_precio.delete(0, "end")
                txt_piezas.delete("1.0", "end")
                txt_notas.delete("1.0", "end")
                actualizar_tabla()
                messagebox.showinfo("SGETV", "Tarea registrada correctamente")
            except mysql.connector.Error as e:
                messagebox.showerror("SGETV", f"Error al guardar tarea: {e}")
            finally:
                if db:
                    db.close()

        def actualizar_tabla():
            for item in tabla_tareas.get_children():
                tabla_tareas.delete(item)

            db = None
            try:
                db = conectar()
                cursor = db.cursor()
                cursor.execute("""SELECT id_tarea, rep_rea, rep_time, imp_tarea FROM reparaciones 
                                 WHERE id_rep = %s ORDER BY id_tarea DESC""", (id_equipo,))
                total_acum = 0
                for id_tarea, desc, tiempo, precio in cursor.fetchall():
                    tabla_tareas.insert("", "end", values=(id_tarea, desc, tiempo or "-", f"€ {float(precio):.2f}" if precio else "€ 0.00"))
                    total_acum += float(precio) if precio else 0

                lbl_total.config(text=f"€ {total_acum:.2f}")
            except mysql.connector.Error as e:
                messagebox.showerror("SGETV", f"Error al cargar tareas: {e}")
            finally:
                if db:
                    db.close()

        def eliminar_tarea():
            item = tabla_tareas.selection()
            if not item:
                messagebox.showwarning("SGETV", "Selecciona una tarea para eliminar")
                return

            if not messagebox.askyesno("Confirmar", "¿Eliminar esta tarea?"):
                return

            db = None
            try:
                db = conectar()
                cursor = db.cursor()
                id_tarea = tabla_tareas.item(item)["values"][0]
                cursor.execute("DELETE FROM reparaciones WHERE id_tarea = %s", (id_tarea,))
                db.commit()

                self.registrar_auditoria(db, "reparaciones", id_tarea, "DELETE", None, None)

                actualizar_tabla()
                messagebox.showinfo("SGETV", "Tarea eliminada correctamente")
            except mysql.connector.Error as e:
                messagebox.showerror("SGETV", f"Error al eliminar tarea: {e}")
            finally:
                if db:
                    db.close()

        def cerrar_reparacion():
            db = None
            try:
                db = conectar()
                cursor = db.cursor()

                cursor.execute("SELECT COALESCE(SUM(imp_tarea), 0) FROM reparaciones WHERE id_rep = %s", (id_equipo,))
                total_precio = float(cursor.fetchone()[0])

                if total_precio == 0:
                    messagebox.showwarning("SGETV", "No hay tareas registradas")
                    return

                if messagebox.askyesno("Confirmar", f"¿Cerrar reparación? Total: € {total_precio:.2f}"):
                    fecha_salida = datetime.now().date()
                    cursor.execute("UPDATE recepciones_despachos SET f_sal = %s, total = %s, estado_id = 4 WHERE id_rep = %s",
                                 (fecha_salida, total_precio, id_equipo))
                    db.commit()

                    self.registrar_auditoria(db, "recepciones_despachos", id_equipo, "UPDATE", None, {"estado": "Cerrada"})

                    messagebox.showinfo("SGETV", f"Reparación cerrada. Total: € {total_precio:.2f}")
                    ventana.destroy()
                    self.actualizar_tabla_registro()
                    self.cargar_registros_filtrados()
            except mysql.connector.Error as e:
                messagebox.showerror("SGETV", f"Error al cerrar reparación: {e}")
            finally:
                if db:
                    db.close()

        def mostrar_presupuesto():
            top_diag = tk.Toplevel(ventana)
            top_diag.title("Generar Presupuesto")
            top_diag.geometry("500x350")
            top_diag.grab_set()
            top_diag.attributes('-topmost', True)
            top_diag.lift()
            top_diag.focus()

            frame_diag = ttk.Frame(top_diag, padding=10)
            frame_diag.pack(fill="both", expand=True)

            ttk.Label(frame_diag, text="Descripción del trabajo:").pack(anchor="w", pady=5)
            txt_presup = self.crear_text_field(frame_diag, height=6, width=60)
            txt_presup.pack(fill="x", pady=5)

            ttk.Label(frame_diag, text="Importe estimado (€):").pack(anchor="w", pady=5)
            txt_importe = ttk.Entry(frame_diag, width=20)
            txt_importe.pack(anchor="w", pady=5)

            def guardar_presupuesto():
                desc = txt_presup.get("1.0", "end").strip()
                importe_txt = txt_importe.get().strip()

                if not desc or not importe_txt:
                    messagebox.showwarning("SGETV", "Completa todos los campos")
                    return

                try:
                    importe = float(importe_txt.replace(",", "."))
                except ValueError:
                    messagebox.showwarning("SGETV", "Importe inválido")
                    return

                db = None
                try:
                    db = conectar()
                    cursor = db.cursor()
                    cursor.execute("""INSERT INTO presupuestos (id_rep, descripcion_trabajo, importe_estimado)
                                     VALUES (%s, %s, %s)""", (id_equipo, desc, importe))
                    db.commit()

                    self.registrar_auditoria(db, "presupuestos", None, "INSERT", None, {"importe": importe})

                    messagebox.showinfo("SGETV", "Presupuesto registrado correctamente")
                    top_diag.destroy()
                except mysql.connector.Error as e:
                    messagebox.showerror("SGETV", f"Error: {e}")
                finally:
                    if db:
                        db.close()

            ttk.Button(frame_diag, text="Guardar presupuesto", command=guardar_presupuesto).pack(pady=10)

        ttk.Button(btn_frame, text="Guardar Tarea", command=guardar_tarea).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Generar Presupuesto", command=mostrar_presupuesto).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Eliminar Tarea", command=eliminar_tarea).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cerrar Reparación", command=cerrar_reparacion).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cerrar", command=ventana.destroy).pack(side="right", padx=5)

        frame_tabla = ttk.LabelFrame(container, text=" Tareas Registradas ", padding=5)
        frame_tabla.pack(fill="both", expand=True, pady=(0, 10))

        tabla_tareas = ttk.Treeview(frame_tabla, columns=("id", "descripcion", "tiempo", "precio"), show="headings", height=10)
        tabla_tareas.heading("id", text="ID")
        tabla_tareas.heading("descripcion", text="DESCRIPCIÓN")
        tabla_tareas.heading("tiempo", text="TIEMPO")
        tabla_tareas.heading("precio", text="PRECIO")

        tabla_tareas.column("id", width=50, anchor="center")
        tabla_tareas.column("descripcion", width=500)
        tabla_tareas.column("tiempo", width=150)
        tabla_tareas.column("precio", width=100, anchor="e")

        scroll = ttk.Scrollbar(frame_tabla, orient="vertical", command=tabla_tareas.yview)
        tabla_tareas.configure(yscrollcommand=scroll.set)
        tabla_tareas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        actualizar_tabla()

    def recargar_estadisticas(self):
        self.lbl_total_reparaciones.config(text="Total Reparaciones: 0")
        self.lbl_ingresos_totales.config(text="Ingresos Totales: € 0.00")
        self.lbl_precio_promedio.config(text="Precio Promedio: € 0.00")
        self.lbl_equipos_reparados.config(text="Equipos Únicos: 0")
        self.lbl_clientes_totales.config(text="Clientes Totales: 0")
        self.txt_stats_equipos.delete("1.0", "end")
        self.txt_stats_clientes.delete("1.0", "end")

        db = None
        try:
            db = conectar()
            cursor = db.cursor()

            periodo = self.combo_periodo.get()
            fecha_filtro = ""
            if periodo == "Este mes":
                hoy = datetime.now()
                fecha_inicio = hoy.replace(day=1).date()
                fecha_filtro = f"AND rd.f_entr >= '{fecha_inicio}'"
            elif periodo == "Este año":
                hoy = datetime.now()
                fecha_inicio = hoy.replace(month=1, day=1).date()
                fecha_filtro = f"AND rd.f_entr >= '{fecha_inicio}'"

            cursor.execute(f"SELECT COUNT(*) FROM recepciones_despachos rd WHERE rd.f_sal IS NOT NULL {fecha_filtro}")
            total_reparaciones = cursor.fetchone()[0]

            cursor.execute(f"SELECT COALESCE(SUM(total), 0) FROM recepciones_despachos rd WHERE rd.f_sal IS NOT NULL {fecha_filtro}")
            ingresos = float(cursor.fetchone()[0])

            cursor.execute(f"SELECT COUNT(DISTINCT nb_eqp) FROM recepciones_despachos rd WHERE rd.f_sal IS NOT NULL {fecha_filtro}")
            equipos_unicos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM clientes")
            clientes_totales = cursor.fetchone()[0]

            promedio = ingresos / total_reparaciones if total_reparaciones > 0 else 0

            self.lbl_total_reparaciones.config(text=f"Total Reparaciones: {total_reparaciones}")
            self.lbl_ingresos_totales.config(text=f"Ingresos Totales: € {ingresos:.2f}")
            self.lbl_precio_promedio.config(text=f"Precio Promedio: € {promedio:.2f}")
            self.lbl_equipos_reparados.config(text=f"Equipos Únicos: {equipos_unicos}")
            self.lbl_clientes_totales.config(text=f"Clientes Totales: {clientes_totales}")

            cursor.execute(f"""SELECT rd.nb_eqp, COUNT(*) as cantidad, COALESCE(SUM(rd.total), 0) as ingresos 
                              FROM recepciones_despachos rd 
                              WHERE rd.f_sal IS NOT NULL {fecha_filtro}
                              GROUP BY rd.nb_eqp 
                              ORDER BY cantidad DESC LIMIT 10""")
            self.txt_stats_equipos.delete("1.0", "end")
            for equipo, cantidad, ingresos_eq in cursor.fetchall():
                self.txt_stats_equipos.insert("end", f"• {equipo}: {cantidad} reparaciones (€ {float(ingresos_eq):.2f})\n")

            cursor.execute(f"""SELECT c.nombre, COUNT(*) as cantidad, COALESCE(SUM(rd.total), 0) as ingresos 
                              FROM recepciones_despachos rd 
                              LEFT JOIN clientes c ON rd.id_cliente = c.id_cli
                              WHERE rd.f_sal IS NOT NULL {fecha_filtro}
                              GROUP BY c.id_cli 
                              ORDER BY cantidad DESC LIMIT 10""")
            self.txt_stats_clientes.delete("1.0", "end")
            for cliente, cantidad, ingresos_cli in cursor.fetchall():
                self.txt_stats_clientes.insert("end", f"• {cliente or 'Sin cliente'}: {cantidad} reparaciones (€ {float(ingresos_cli):.2f})\n")

        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al cargar estadísticas: {e}")
        finally:
            if db:
                db.close()

    def seleccionar_ruta_respaldo(self):
        ruta = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if ruta:
            self.txt_ruta_respaldo.delete(0, "end")
            self.txt_ruta_respaldo.insert(0, ruta)

    def obtener_ruta_mysqldump(self):
        ruta = shutil.which("mysqldump")
        if ruta and os.path.isfile(ruta):
            return ruta

        if SISTEMA == "linux":
            rutas_comunes = [
                "/usr/bin/mysqldump",
                "/usr/local/bin/mysqldump",
                "/opt/lampp/bin/mysqldump",
            ]
            for ruta_posible in rutas_comunes:
                if os.path.isfile(ruta_posible):
                    return ruta_posible
        else:
            posibles = [
                r"C:\xampp\mysql\bin\mysqldump.exe",
                r"C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin\mysqldump.exe",
            ]

            for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
                if not base:
                    continue

                mysql_dir = os.path.join(base, "MySQL")
                if os.path.isdir(mysql_dir):
                    try:
                        for carpeta in os.listdir(mysql_dir):
                            posibles.append(os.path.join(mysql_dir, carpeta, "bin", "mysqldump.exe"))
                    except OSError:
                        pass

                mariadb_dir = os.path.join(base, "MariaDB")
                if os.path.isdir(mariadb_dir):
                    try:
                        for carpeta in os.listdir(mariadb_dir):
                            posibles.append(os.path.join(mariadb_dir, carpeta, "bin", "mysqldump.exe"))
                            posibles.append(os.path.join(mariadb_dir, carpeta, "bin", "mariadb-dump.exe"))
                    except OSError:
                        pass

            for ruta_posible in posibles:
                if os.path.isfile(ruta_posible):
                    return ruta_posible

        return None

    def crear_respaldo_manual(self):
        ruta_destino = self.txt_ruta_respaldo.get().strip()
        if not ruta_destino or not os.path.isdir(ruta_destino):
            messagebox.showwarning("SGETV", "Selecciona una ruta válida")
            return

        def log(msg):
            self.txt_log_respaldo.insert("end", msg + "\n")
            self.txt_log_respaldo.see("end")
            self.root.update()

        log("=== INICIANDO RESPALDO ===")
        log(f"Destino: {ruta_destino}")
        log(f"Fecha: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"telereparo_respaldo_{timestamp}.sql"
            ruta_archivo = os.path.join(ruta_destino, nombre_archivo)

            ruta_mysqldump = self.obtener_ruta_mysqldump()
            if not ruta_mysqldump:
                log("✗ No se encontró mysqldump en PATH ni en rutas comunes de instalación")
                messagebox.showerror(
                    "SGETV",
                    "Error al crear respaldo. Verifica que MySQL/MariaDB esté instalado y que mysqldump esté disponible.",
                )
                return

            cmd = [
                ruta_mysqldump,
                f"--host={DB_CONFIG['host']}",
                f"--user={DB_CONFIG['user']}",
                f"--password={DB_CONFIG['password']}",
                "--single-transaction",
                "--quick",
                "--lock-tables=false",
                DB_CONFIG['database'],
            ]
            
            if SISTEMA == "linux" and "unix_socket" in DB_CONFIG:
                cmd.append(f"--socket={DB_CONFIG['unix_socket']}")

            with open(ruta_archivo, "w", encoding="utf-8", errors="replace") as archivo_sql:
                resultado = subprocess.run(
                    cmd,
                    stdout=archivo_sql,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )

            if resultado.returncode == 0 and os.path.exists(ruta_archivo):
                db = None
                try:
                    db = conectar()
                    cursor = db.cursor()
                    tamanio = os.path.getsize(ruta_archivo)
                    cursor.execute("""INSERT INTO copias_seguridad (nombre_archivo, ruta_archivo, tamanio_bytes, estado)
                                     VALUES (%s, %s, %s, %s)""",
                                 (nombre_archivo, ruta_archivo, tamanio, "Exitosa"))
                    db.commit()
                except Exception:
                    pass
                finally:
                    if db:
                        db.close()

                log(f"✓ Respaldo completado exitosamente")
                log(f"Archivo: {ruta_archivo}")
                log(f"Tamaño: {tamanio / 1024 / 1024:.2f} MB")
                messagebox.showinfo("SGETV", f"Respaldo completado en:\n{ruta_archivo}")
            else:
                detalle_error = (resultado.stderr or "Error desconocido").strip()
                log("✗ Error al crear respaldo")
                log(f"Detalle: {detalle_error}")
                messagebox.showerror("SGETV", f"Error al crear respaldo:\n{detalle_error}")

        except Exception as e:
            log(f"✗ Error: {e}")
            messagebox.showerror("SGETV", f"Error: {e}")

    def ver_historial_respaldos(self):
        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            cursor.execute("SELECT nombre_archivo, DATE_FORMAT(fecha_creacion, '%d-%m-%Y %H:%i'), tamanio_bytes, estado FROM copias_seguridad ORDER BY fecha_creacion DESC LIMIT 20")

            historial = "HISTORIAL DE RESPALDOS\n" + "="*80 + "\n\n"
            for nombre, fecha, tamanio, estado in cursor.fetchall():
                tamanio_mb = tamanio / 1024 / 1024 if tamanio else 0
                historial += f"• {nombre}\n"
                historial += f"  Fecha: {fecha} | Tamaño: {tamanio_mb:.2f} MB | Estado: {estado}\n\n"

            self.txt_log_respaldo.delete("1.0", "end")
            self.txt_log_respaldo.insert("1.0", historial)

        except mysql.connector.Error as e:
            messagebox.showerror("SGETV", f"Error al cargar historial: {e}")
        finally:
            if db:
                db.close()

    def registrar_auditoria(self, db, tabla, id_registro, tipo_cambio, datos_anteriores, datos_nuevos):
        try:
            cursor = db.cursor()
            cursor.execute("""INSERT INTO auditoria_cambios 
                             (tabla_modificada, id_registro, tipo_cambio, datos_anteriores, datos_nuevos, usuario, fecha_cambio)
                             VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                         (tabla, id_registro, tipo_cambio, 
                          json.dumps(datos_anteriores) if datos_anteriores else None,
                          json.dumps(datos_nuevos) if datos_nuevos else None,
                          "Admin", datetime.now()))
            db.commit()
        except mysql.connector.Error:
            pass

    def comprobar_conexion(self):
        self.txt_log.delete("1.0", "end")
        self.append_log("=== COMPROBACIÓN DE CONEXIÓN ===")

        db = None
        try:
            db = conectar()
            cursor = db.cursor()
            self.append_log("✓ Conexión exitosa a la base de datos")

            cursor.execute("SHOW TABLES")
            tablas = [t[0] for t in cursor.fetchall()]
            self.append_log(f"✓ Tablas encontradas: {len(tablas)}")

            for tabla in tablas:
                cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
                total = cursor.fetchone()[0]
                self.append_log(f"  - {tabla}: {total} registros")

            self.append_log("\n=== COMPROBACIÓN FINALIZADA ===")
        except mysql.connector.Error as e:
            self.append_log(f"✗ ERROR de MySQL: {e}")
            messagebox.showerror("SGETV", f"Error de conexión: {e}")
        finally:
            if db:
                db.close()

    def append_log(self, texto):
        self.txt_log.insert("end", texto + "\n")
        self.txt_log.see("end")


if __name__ == "__main__":
    app_root = tk.Tk()
    SGETVApp(app_root)
    app_root.mainloop()