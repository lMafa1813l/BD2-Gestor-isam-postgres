import os
import math
from PyQt6.QtWidgets import (
    QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QSpinBox, QLineEdit, QPushButton, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QFileDialog,
    QRadioButton, QButtonGroup, QFrame, QSizePolicy, QMessageBox,
    QSplitter, QApplication, QHeaderView, QTabWidget, QScrollArea, QCheckBox
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QPainterPath, QLinearGradient,
    QRadialGradient
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QPoint


# ─────────────────────────────────────────────
#  PALETA DE COLORES
# ─────────────────────────────────────────────
class T:
    BG1      = "#0f1117"
    BG2      = "#161921"
    BG3      = "#1c2030"
    BG4      = "#252a3a"
    BORDE    = "#2a3045"
    BORDE_ACT= "#3d6bcc"
    TXT      = "#c8cdd8"
    TXT_W    = "#edf0f5"
    TXT_D    = "#6b7280"
    ACC      = "#3d6bcc"
    ACC_H    = "#4f7de0"
    ACC_S    = "#1a2744"
    OK       = "#22c55e"
    WARN     = "#f59e0b"
    ERR      = "#ef4444"
    PURPLE   = "#7c3aed"


class TablaSmooth(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        pasos = 30 if delta > 0 else -30
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() - pasos)
        event.accept()


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _cabecera(titulo, sub=""):
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {T.ACC_S}, stop:1 {T.BG2});
            border-bottom: 1px solid {T.BORDE}; padding: 14px;
        }}
    """)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(20, 12, 20, 12)
    lay.setSpacing(3)
    t = QLabel(titulo)
    t.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
    t.setStyleSheet(f"color:{T.TXT_W}; background:transparent; border:none;")
    lay.addWidget(t)
    if sub:
        s = QLabel(sub)
        s.setFont(QFont("Segoe UI", 10))
        s.setStyleSheet(f"color:{T.TXT_D}; background:transparent; border:none;")
        lay.addWidget(s)
    return f


def _sep():
    l = QFrame()
    l.setFrameShape(QFrame.Shape.HLine)
    l.setStyleSheet(f"background:{T.BORDE}; max-height:1px;")
    return l


_BTN_PRI = f"""
    QPushButton {{
        background:{T.ACC}; color:white; font-family:'Segoe UI';
        font-weight:600; font-size:13px; border:none;
        border-radius:6px; padding:9px 22px;
    }}
    QPushButton:hover {{ background:{T.ACC_H}; }}
    QPushButton:pressed {{ background:#2f5ab3; }}
"""
_BTN_SEC = f"""
    QPushButton {{
        background:transparent; color:{T.TXT}; font-family:'Segoe UI';
        font-weight:500; font-size:13px; border:1px solid {T.BORDE};
        border-radius:6px; padding:9px 22px;
    }}
    QPushButton:hover {{ background:{T.BG3}; border-color:{T.TXT_D}; }}
"""
_SPIN = f"""
    QSpinBox {{
        background:{T.BG3}; border:1px solid {T.BORDE};
        border-radius:6px; padding:6px 12px; color:{T.TXT_W};
        font-family:'Segoe UI'; font-size:13px;
    }}
    QSpinBox:focus {{ border-color:{T.ACC}; }}
"""
_BTN_SPIN = f"""
    QPushButton {{
        background:{T.BG4}; color:{T.TXT_W}; font-family:'Segoe UI';
        font-size:16px; font-weight:bold; border:1px solid {T.BORDE};
        border-radius:6px; min-width:36px; min-height:36px;
        max-width:36px; max-height:36px;
    }}
    QPushButton:hover {{ background:{T.ACC_S}; border-color:{T.ACC}; }}
    QPushButton:pressed {{ background:{T.ACC}; }}
"""


# ─────────────────────────────────────────────
#  HELPERS AVL (recorridos sin tocar Avl.py)
# ─────────────────────────────────────────────
def _inorden_claves(avl):
    """Devuelve las claves en orden inorden del árbol AVL."""
    claves = []
    def _trav(nodo):
        if nodo is None:
            return
        _trav(nodo.izquierda)
        claves.append(nodo.clave)
        _trav(nodo.derecha)
    if avl and avl.raiz:
        _trav(avl.raiz)
    return claves


def _claves_en_rango(avl, minimo, maximo):
    """Devuelve las claves del AVL dentro de [minimo, maximo]."""
    claves = []
    def _trav(nodo):
        if nodo is None:
            return
        if minimo < nodo.clave:
            _trav(nodo.izquierda)
        if minimo <= nodo.clave <= maximo:
            claves.append(nodo.clave)
        if nodo.clave < maximo:
            _trav(nodo.derecha)
    if avl and avl.raiz:
        _trav(avl.raiz)
    return claves


# ─────────────────────────────────────────────
#  DIÁLOGO: CONFIGURACIÓN DEL DISCO
# ─────────────────────────────────────────────
class ConfigDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disco de Fabianes")
        self.setFixedSize(520, 400)
        self.setStyleSheet(f"""
            QDialog {{ background:{T.BG1}; }}
            QLabel {{ color:{T.TXT}; font-family:'Segoe UI'; font-size:12px; background:transparent; }}
            {_SPIN}
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_cabecera(
            "Configuración del disco",
            "Defina la geometría del disco virtual"
        ))
        form_w = QWidget()
        form_w.setStyleSheet(f"background:{T.BG1};")
        form = QGridLayout(form_w)
        form.setContentsMargins(28, 20, 28, 10)
        form.setSpacing(14)
        form.setColumnStretch(1, 1)
        params = [
            ("Número de platos",          1,  16,   2),
            ("Pistas por superficie",     1, 1024, 10),
            ("Sectores por pista",        1,  63,  20),
            ("Tamaño de sector (bytes)",  1, 4096, 16),
        ]
        self.inputs = []
        for i, (label, mn, mx, default) in enumerate(params):
            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 11))
            spin = QSpinBox()
            spin.setRange(mn, mx)
            spin.setValue(default)
            spin.setFixedHeight(38)
            spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_minus = QPushButton("−")
            btn_minus.setStyleSheet(_BTN_SPIN)
            btn_minus.clicked.connect(spin.stepDown)
            btn_plus = QPushButton("+")
            btn_plus.setStyleSheet(_BTN_SPIN)
            btn_plus.clicked.connect(spin.stepUp)
            self.inputs.append(spin)
            form.addWidget(lbl,       i, 0)
            form.addWidget(btn_minus, i, 1)
            form.addWidget(spin,      i, 2)
            form.addWidget(btn_plus,  i, 3)
        layout.addWidget(form_w, stretch=1)
        btn_f = QWidget()
        btn_f.setStyleSheet(f"background:{T.BG1};")
        bl = QHBoxLayout(btn_f)
        bl.setContentsMargins(28, 10, 28, 20)
        b1 = QPushButton("Restablecer")
        b1.setStyleSheet(_BTN_SEC)
        b1.clicked.connect(self._defaults)
        b2 = QPushButton("Iniciar simulación  →")
        b2.setStyleSheet(_BTN_PRI)
        b2.clicked.connect(self.accept)
        bl.addWidget(b1)
        bl.addStretch()
        bl.addWidget(b2)
        layout.addWidget(btn_f)
        self.setLayout(layout)

    def _defaults(self):
        for s, v in zip(self.inputs, [2, 10, 20, 16]):
            s.setValue(v)

    def get_valores(self):
        return {
            "platos":  self.inputs[0].value(),
            "pistas":  self.inputs[1].value(),
            "sectores":self.inputs[2].value(),
            "tamano":  self.inputs[3].value()
        }


# ─────────────────────────────────────────────
#  DIÁLOGO: SELECCIÓN DE ARCHIVOS
# ─────────────────────────────────────────────
class ArchivosDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disco de Fabianes")
        self.setFixedSize(560, 400)
        self.setStyleSheet(f"""
            QDialog {{ background:{T.BG1}; }}
            QLabel {{ color:{T.TXT}; font-family:'Segoe UI'; font-size:12px; background:transparent; }}
        """)
        self.ruta_txt = ""
        self.ruta_csv = ""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_cabecera(
            "Cargar archivos",
            "Seleccione la estructura (.txt) y los datos (.csv)"
        ))
        cw = QWidget()
        cw.setStyleSheet(f"background:{T.BG1};")
        cl = QHBoxLayout(cw)
        cl.setContentsMargins(24, 20, 24, 10)
        cl.setSpacing(14)
        self.card_txt, self.lbl_txt, self.ico_txt = self._card("Estructura SQL", ".txt", self._sel_txt)
        self.card_csv, self.lbl_csv, self.ico_csv = self._card("Datos",          ".csv", self._sel_csv)
        cl.addWidget(self.card_txt)
        cl.addWidget(self.card_csv)
        layout.addWidget(cw, stretch=1)

        self.chk_headers = QCheckBox("El archivo CSV contiene nombres de columnas en la primera fila")
        self.chk_headers.setChecked(True)
        self.chk_headers.setStyleSheet(f"color:{T.TXT}; font-family:'Segoe UI'; font-size:12px; margin-left: 24px; padding-bottom: 10px;")
        layout.addWidget(self.chk_headers)

        bf = QWidget()
        bf.setStyleSheet(f"background:{T.BG1};")
        bfl = QHBoxLayout(bf)
        bfl.setContentsMargins(24, 10, 24, 20)
        self.btn_ok = QPushButton("Cargar y continuar  →")
        self.btn_ok.setEnabled(False)
        self.btn_ok.setStyleSheet(f"""
            QPushButton {{
                background:{T.BG4}; color:{T.TXT_D}; font-family:'Segoe UI';
                font-weight:600; font-size:13px; border:none;
                border-radius:6px; padding:9px 22px;
            }}
        """)
        self.btn_ok.clicked.connect(self.accept)
        bfl.addStretch()
        bfl.addWidget(self.btn_ok)
        layout.addWidget(bf)
        self.setLayout(layout)

    def _card(self, titulo, ext, click):
        c = QFrame()
        c.setFixedHeight(140)
        c.setStyleSheet(f"""
            QFrame {{ background:{T.BG2}; border:1px dashed {T.BORDE}; border-radius:10px; }}
            QFrame:hover {{ border-color:{T.ACC}; background:{T.BG3}; }}
        """)
        c.setCursor(Qt.CursorShape.PointingHandCursor)
        inner = QVBoxLayout(c)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.setSpacing(8)
        ico = QLabel("📄")
        ico.setFont(QFont("Segoe UI", 24))
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("border:none;")
        t = QLabel(titulo)
        t.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color:{T.TXT_W}; border:none;")
        s = QLabel(f"Clic para seleccionar {ext}")
        s.setFont(QFont("Segoe UI", 9))
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet(f"color:{T.TXT_D}; border:none;")
        inner.addWidget(ico)
        inner.addWidget(t)
        inner.addWidget(s)
        c.mousePressEvent = lambda e: click()
        return c, s, ico

    def _sel_txt(self):
        r, _ = QFileDialog.getOpenFileName(self, "Seleccionar .txt", "", "*.txt")
        if r and r.endswith(".txt"):
            self.ruta_txt = r
            self.ico_txt.setText("✅")
            self.lbl_txt.setText(os.path.basename(r))
            self.lbl_txt.setStyleSheet(f"color:{T.OK}; border:none;")
            self.card_txt.setStyleSheet(f"QFrame {{ background:{T.BG2}; border:1px solid #1a4a2e; border-radius:10px; }}")
        self._check()

    def _sel_csv(self):
        r, _ = QFileDialog.getOpenFileName(self, "Seleccionar .csv", "", "*.csv")
        if r and r.endswith(".csv"):
            self.ruta_csv = r
            self.ico_csv.setText("✅")
            self.lbl_csv.setText(os.path.basename(r))
            self.lbl_csv.setStyleSheet(f"color:{T.OK}; border:none;")
            self.card_csv.setStyleSheet(f"QFrame {{ background:{T.BG2}; border:1px solid #1a4a2e; border-radius:10px; }}")
        self._check()

    def _check(self):
        ok = bool(self.ruta_txt and self.ruta_csv)
        self.btn_ok.setEnabled(ok)
        if ok:
            self.btn_ok.setStyleSheet(_BTN_PRI)


# ─────────────────────────────────────────────
#  WIDGET: DISCO CIRCULAR
# ─────────────────────────────────────────────
class DiscoWidget(QWidget):
    def __init__(self, disco, parent=None):
        super().__init__(parent)
        self.disco = disco
        self.plato_actual = 0
        self.superficie_actual = 0
        self.sectores_resaltados = set()
        self.sector_hover = None
        self.setMinimumSize(300, 300)
        self.setMouseTracking(True)

    def resaltar_sectores(self, lbas):
        self.sectores_resaltados = set(lbas)
        self.update()

    def limpiar_resaltado(self):
        self.sectores_resaltados.clear()
        self.update()

    def set_vista(self, p, s):
        self.plato_actual = p
        self.superficie_actual = s
        self.update()

    def _geo(self):
        sz = min(self.width(), self.height()) - 16
        cx, cy = self.width() / 2, self.height() / 2
        mr = sz / 2
        np = self.disco.pistas_por_superficie
        ns = self.disco.sectores_por_pista
        ih = mr * 0.12
        rw = (mr - ih) / np
        ss = 360.0 / ns
        return cx, cy, mr, ih, rw, ss, np, ns

    def _sector_at(self, pos):
        cx, cy, mr, ih, rw, ss, np, ns = self._geo()
        dx, dy = pos.x() - cx, -(pos.y() - cy)
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < ih or dist > mr:
            return None, None
        ang = math.degrees(math.atan2(dy, dx)) % 360
        sec = min(int(ang / ss), ns - 1)
        for i in range(np):
            o_r = mr - i * rw
            i_r = mr - (i + 1) * rw
            if i_r <= dist <= o_r:
                return i, sec
        return None, None

    def mouseMoveEvent(self, event):
        pi, se = self._sector_at(event.position())
        nh = (pi, se) if pi is not None else None
        if nh != self.sector_hover:
            self.sector_hover = nh
            self.update()
        if pi is not None:
            lba = self.disco._chs_a_lba(self.plato_actual, self.superficie_actual, pi, se)
            so = self.disco.sectores[lba]
            t = f"<div style='font-family:Segoe UI;font-size:11px;padding:3px;'>"
            t += f"<b>LBA {lba}</b> · P{self.plato_actual} S{self.superficie_actual} Pi{pi} Se{se}<br>"
            if so and so.tamano_ocupado > 0:
                t += f"Uso: {so.tamano_ocupado}/{self.disco.tamano_sector} bytes<br>"
                t += "Reg: " + ", ".join(set(f['id_registro'] for f in so.fragmentos))
            else:
                t += "Vacío"
            t += "</div>"
            self.setToolTip(t)
        else:
            self.setToolTip("")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(T.BG2))
        cx, cy, mr, ih, rw, ss, np, ns = self._geo()
        gr = QRadialGradient(cx, cy, mr + 12)
        gr.setColorAt(0.88, QColor(30, 40, 60, 40))
        gr.setColorAt(1.0,  QColor(0, 0, 0, 0))
        p.setBrush(QBrush(gr))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), mr + 10, mr + 10)
        reg_lba = {}
        for _, ubs in self.disco.mapa_ubicacion_fisica.items():
            lbas_unicos_del_registro = set(lb for lb, _, _ in ubs)
            for lb in lbas_unicos_del_registro:
                reg_lba[lb] = reg_lba.get(lb, 0) + 1
        C_VACIO = QColor("#1a2e1a")
        C_OCUP  = QColor("#7a5c10")
        C_BUSC  = QColor("#2563eb")
        C_COMP  = QColor("#dc2626")
        C_HOV   = QColor("#d0d0d0")
        for pi in range(np):
            o_r = mr - pi * rw
            i_r = mr - (pi + 1) * rw
            for se in range(ns):
                lba = self.disco._chs_a_lba(self.plato_actual, self.superficie_actual, pi, se)
                so  = self.disco.sectores[lba]
                hov = (self.sector_hover == (pi, se))
                if hov:
                    col = C_HOV
                elif lba in self.sectores_resaltados:
                    col = C_COMP if reg_lba.get(lba, 0) > 1 else C_BUSC
                elif so and so.tamano_ocupado > 0:
                    col = C_OCUP
                else:
                    col = C_VACIO
                self._wedge(p, cx, cy, o_r, i_r, se * ss, ss, col, hov)
        p.setPen(QPen(QColor(T.BORDE), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), mr, mr)
        cg = QRadialGradient(cx, cy, ih)
        cg.setColorAt(0, QColor("#2a2f40"))
        cg.setColorAt(1, QColor(T.BG1))
        p.setPen(QPen(QColor(T.BORDE), 1))
        p.setBrush(QBrush(cg))
        p.drawEllipse(QPointF(cx, cy), ih, ih)
        dg = QRadialGradient(cx - 1, cy - 1, 5)
        dg.setColorAt(0, QColor("#8899aa"))
        dg.setColorAt(1, QColor("#3a4555"))
        p.setBrush(QBrush(dg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 5, 5)

    def _wedge(self, p, cx, cy, o_r, i_r, sd, sp, col, hov=False):
        path = QPainterPath()
        sa = math.radians(sd)
        path.moveTo(cx + o_r * math.cos(sa), cy - o_r * math.sin(sa))
        path.arcTo(QRectF(cx-o_r, cy-o_r, 2*o_r, 2*o_r), sd, sp)
        path.arcTo(QRectF(cx-i_r, cy-i_r, 2*i_r, 2*i_r), sd + sp, -sp)
        path.closeSubpath()
        p.setBrush(QBrush(col))
        p.setPen(QPen(QColor(T.ACC if hov else "#1f2535"), 0.6))
        p.drawPath(path)


# ─────────────────────────────────────────────
#  WIDGET: ÁRBOL AVL
# ─────────────────────────────────────────────
class AVLCanvas(QWidget):
    """Dibuja el árbol AVL con QPainter. Se coloca dentro de un QScrollArea."""

    NODE_R = 22
    H_GAP  = 54
    V_GAP  = 72

    def __init__(self, parent=None):
        super().__init__(parent)
        self.arbol      = None      # AVLIndex
        self.resaltados = set()     # claves a destacar
        self._pos       = {}        # id(nodo) -> (px, py)
        self.setMinimumSize(400, 300)

    # ── API pública ─────────────────────────────────────────────────────
    def set_arbol(self, avl_index):
        self.arbol = avl_index
        self.resaltados = set()
        self._calcular_pos()
        self._ajustar_tamano()
        self.update()

    def resaltar(self, claves):
        self.resaltados = set(claves)
        self.update()

    def limpiar(self):
        self.resaltados = set()
        self.update()

    # ── Posicionamiento inorden ─────────────────────────────────────────
    def _calcular_pos(self):
        self._pos = {}
        if not self.arbol or not self.arbol.raiz:
            return
        cnt = [0]
        def _inord(nodo, prof):
            if nodo is None:
                return
            _inord(nodo.izquierda, prof + 1)
            x = cnt[0] * self.H_GAP + self.NODE_R + 20
            y = prof    * self.V_GAP + self.NODE_R + 20
            self._pos[id(nodo)] = (x, y)
            cnt[0] += 1
            _inord(nodo.derecha, prof + 1)
        _inord(self.arbol.raiz, 0)

    def _ajustar_tamano(self):
        if not self._pos:
            self.setMinimumSize(400, 300)
            return
        mx = max(x for x, _ in self._pos.values()) + self.NODE_R + 30
        my = max(y for _, y in self._pos.values()) + self.NODE_R + 30
        self.setMinimumSize(max(mx, 400), max(my, 300))

    # ── Pintura ─────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(T.BG2))

        if not self.arbol or not self.arbol.raiz or not self._pos:
            p.setPen(QColor(T.TXT_D))
            p.setFont(QFont("Segoe UI", 12))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Sin datos en el árbol.\nRealiza una búsqueda primero.")
            return

        self._draw_edges(p, self.arbol.raiz)
        self._draw_nodes(p, self.arbol.raiz)

    def _draw_edges(self, p, nodo):
        if nodo is None:
            return
        if id(nodo) in self._pos:
            px, py = self._pos[id(nodo)]
            for hijo in (nodo.izquierda, nodo.derecha):
                if hijo and id(hijo) in self._pos:
                    cx, cy = self._pos[id(hijo)]
                    p.setPen(QPen(QColor(T.BORDE), 2))
                    p.drawLine(int(px), int(py), int(cx), int(cy))
        self._draw_edges(p, nodo.izquierda)
        self._draw_edges(p, nodo.derecha)

    def _draw_nodes(self, p, nodo):
        if nodo is None:
            return
        self._draw_nodes(p, nodo.izquierda)
        self._draw_nodes(p, nodo.derecha)

        if id(nodo) not in self._pos:
            return
        x, y = self._pos[id(nodo)]
        r = self.NODE_R
        resaltado = nodo.clave in self.resaltados
        es_raiz   = (nodo is self.arbol.raiz)

        # Sombra
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 70)))
        p.drawEllipse(QPointF(x + 2, y + 2), r, r)

        # Color del nodo
        if resaltado:
            color = QColor(T.OK)          # verde = encontrado
        elif es_raiz:
            color = QColor(T.PURPLE)      # morado = raíz
        else:
            color = QColor(T.ACC)         # azul = normal

        p.setBrush(QBrush(color))
        p.setPen(QPen(QColor("white"), 1.5))
        p.drawEllipse(QPointF(x, y), r, r)

        # Texto clave
        clave = nodo.clave
        if isinstance(clave, float):
            label = f"{clave:.1f}"
        else:
            label = str(clave)
        if len(label) > 6:
            label = label[:5] + "…"
        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.drawText(QRectF(x - r, y - r, r * 2, r * 2),
                   Qt.AlignmentFlag.AlignCenter, label)

        # Factor de balance (esquina superior derecha del nodo)
        def _h(n):
            return n.altura if n else 0
        bal = _h(nodo.izquierda) - _h(nodo.derecha)
        bal_color = QColor(T.OK) if abs(bal) <= 1 else QColor(T.ERR)
        p.setPen(bal_color)
        p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        p.drawText(int(x + r - 6), int(y - r + 10), f"{bal:+d}")


# ─────────────────────────────────────────────
#  ESTILO GLOBAL
# ─────────────────────────────────────────────
_ESTILO = f"""
    QMainWindow, QWidget {{
        background:{T.BG1}; color:{T.TXT}; font-family:'Segoe UI';
    }}
    QGroupBox {{
        background:{T.BG2}; border:1px solid {T.BORDE}; border-radius:8px;
        margin-top:12px; padding:10px; padding-top:22px;
        font-size:11px; font-weight:600; color:{T.ACC};
    }}
    QGroupBox::title {{
        subcontrol-origin:margin; left:12px; padding:2px 8px;
        background:{T.BG2}; border-radius:4px;
    }}
    QTabWidget::pane {{
        background:{T.BG2}; border:1px solid {T.BORDE}; border-radius:8px;
    }}
    QTabBar::tab {{
        background:{T.BG3}; color:{T.TXT_D}; font-family:'Segoe UI';
        font-size:11px; font-weight:600; padding:8px 20px;
        border:1px solid {T.BORDE}; border-bottom:none;
        border-top-left-radius:6px; border-top-right-radius:6px;
        margin-right:2px;
    }}
    QTabBar::tab:selected {{
        background:{T.ACC}; color:white; border-color:{T.ACC};
    }}
    QTabBar::tab:hover:!selected {{
        background:{T.BG4}; color:{T.TXT_W};
    }}
    QComboBox {{
        background:{T.BG3}; border:1px solid {T.BORDE}; border-radius:5px;
        padding:5px 8px; color:{T.TXT_W}; font-size:12px;
    }}
    QComboBox:hover {{ border-color:{T.ACC}; }}
    QComboBox::drop-down {{ border:none; width:22px; }}
    QComboBox QAbstractItemView {{
        background:{T.BG3}; border:1px solid {T.BORDE}; color:{T.TXT_W};
        selection-background-color:{T.ACC};
    }}
    QLineEdit {{
        background:{T.BG3}; border:1px solid {T.BORDE}; border-radius:5px;
        padding:5px 8px; color:{T.TXT_W}; font-size:12px;
    }}
    QLineEdit:focus {{ border-color:{T.ACC}; }}
    QRadioButton {{ color:{T.TXT}; font-size:11px; spacing:5px; }}
    QRadioButton::indicator {{
        width:14px; height:14px; border-radius:7px;
        border:2px solid {T.BORDE}; background:{T.BG3};
    }}
    QRadioButton::indicator:checked {{
        background:{T.ACC}; border-color:{T.ACC};
    }}
    QPushButton {{
        background:{T.ACC}; color:white; font-weight:600; border:none;
        border-radius:5px; padding:6px 14px; font-size:11px;
    }}
    QPushButton:hover {{ background:{T.ACC_H}; }}
    QTableWidget {{
        background:{T.BG2}; alternate-background-color:{T.BG3};
        gridline-color:{T.BORDE}; color:{T.TXT}; font-size:11px;
        border:none; selection-background-color:{T.ACC_S};
        selection-color:{T.TXT_W};
    }}
    QTableWidget::item {{ padding:3px 6px; }}
    QTableWidget::item:selected {{ background:{T.ACC_S}; }}
    QHeaderView::section {{
        background:{T.BG3}; color:{T.TXT}; padding:5px 6px;
        border:none; border-bottom:2px solid {T.ACC};
        font-weight:600; font-size:10px;
    }}
    QLabel {{ font-size:11px; }}
    QScrollBar:vertical {{
        background:{T.BG2}; width:7px; border-radius:3px;
    }}
    QScrollBar::handle:vertical {{
        background:{T.BORDE}; border-radius:3px; min-height:30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
    QScrollBar:horizontal {{
        background:{T.BG2}; height:7px; border-radius:3px;
    }}
    QScrollBar::handle:horizontal {{
        background:{T.BORDE}; border-radius:3px; min-width:30px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
"""


# ─────────────────────────────────────────────
#  VENTANA PRINCIPAL
# ─────────────────────────────────────────────
class VentanaPrincipal(QMainWindow):
    def __init__(self, disco, bd, nombre_tabla):
        super().__init__()
        self.disco        = disco
        self.bd           = bd
        self.nombre_tabla = nombre_tabla
        self.setWindowTitle("Disco de Fabianes — Simulación de Almacenamiento Físico")
        self.resize(1380, 880)
        self.setStyleSheet(_ESTILO)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ═══ PANEL IZQUIERDO ═══
        left = QVBoxLayout()
        left.setSpacing(6)

        titulo_w = QFrame()
        titulo_w.setFixedHeight(40)
        titulo_w.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {T.ACC_S}, stop:1 {T.BG1});
            border-radius:6px;
        """)
        tl = QHBoxLayout(titulo_w)
        tl.setContentsMargins(12, 0, 12, 0)
        t_lbl = QLabel(f"Tabla: {nombre_tabla}")
        t_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        t_lbl.setStyleSheet(f"color:{T.TXT_W}; background:transparent;")
        tl.addWidget(t_lbl)
        cnt   = len(bd.tablas[nombre_tabla]['registros'])
        badge = QLabel(f" {cnt} reg ")
        badge.setFont(QFont("Segoe UI", 9))
        badge.setStyleSheet(f"color:{T.OK}; background:#122e1a; border-radius:8px; padding:1px 8px;")
        tl.addStretch()
        tl.addWidget(badge)
        left.addWidget(titulo_w)

        left.addWidget(self._panel_busqueda())
        left.addWidget(self._panel_info())
        left.addWidget(self._panel_leyenda())
        left.addStretch()

        left_w = QWidget()
        left_w.setFixedWidth(285)
        left_w.setLayout(left)
        root.addWidget(left_w)

        # ═══ PANEL DERECHO ═══
        right = QVBoxLayout()
        right.setSpacing(8)

        # ── Tabs: Disco | Árbol AVL ──
        self.tabs = QTabWidget()
        self.tabs.addTab(self._panel_disco(), " Visualización del Disco")
        self.tabs.addTab(self._panel_avl(),   " Árbol AVL")
        right.addWidget(self.tabs, stretch=5)

        right.addWidget(self._panel_resultados(), stretch=3)

        root.addLayout(right, stretch=1)

    # ─────────────────────────────────────────
    #  PANEL: BÚSQUEDA
    # ─────────────────────────────────────────
    def _panel_busqueda(self):
        g = QGroupBox("Búsqueda")
        lay = QVBoxLayout()
        lay.setSpacing(6)
        lay.setContentsMargins(10, 8, 10, 8)

        rl = QHBoxLayout()
        self.radio_exacta = QRadioButton("Exacta")
        self.radio_rango  = QRadioButton("Rango")
        self.radio_exacta.setChecked(True)
        self.radio_exacta.toggled.connect(self._toggle_modo)
        bg = QButtonGroup(self)
        bg.addButton(self.radio_exacta)
        bg.addButton(self.radio_rango)
        rl.addWidget(self.radio_exacta)
        rl.addWidget(self.radio_rango)
        rl.addStretch()
        lay.addLayout(rl)

        cols = self.bd.tablas[self.nombre_tabla]['columnas']
        self.combo_col = QComboBox()
        self.combo_col.addItems(cols)
        lay.addWidget(self.combo_col)

        self.inp_val = QLineEdit()
        self.inp_val.setPlaceholderText("Valor a buscar...")
        lay.addWidget(self.inp_val)

        self.rng_w = QWidget()
        rl2 = QHBoxLayout(self.rng_w)
        rl2.setContentsMargins(0, 0, 0, 0)
        rl2.setSpacing(6)
        self.inp_min = QLineEdit()
        self.inp_min.setPlaceholderText("Mín")
        self.inp_max = QLineEdit()
        self.inp_max.setPlaceholderText("Máx")
        rl2.addWidget(self.inp_min)
        rl2.addWidget(self.inp_max)
        self.rng_w.setVisible(False)
        lay.addWidget(self.rng_w)

        bl = QHBoxLayout()
        b1 = QPushButton("Buscar")
        b1.clicked.connect(self._buscar)
        b2 = QPushButton("Limpiar")
        b2.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{T.TXT_D};
                border:1px solid {T.BORDE}; border-radius:5px;
                padding:6px 12px; font-size:11px; }}
            QPushButton:hover {{ background:{T.BG3}; color:{T.TXT}; }}
        """)
        b2.clicked.connect(self._limpiar)
        bl.addWidget(b1, stretch=2)
        bl.addWidget(b2, stretch=1)
        lay.addLayout(bl)

        g.setLayout(lay)
        return g

    def _toggle_modo(self, exacta):
        self.inp_val.setVisible(exacta)
        self.rng_w.setVisible(not exacta)

    # ─────────────────────────────────────────
    #  PANEL: INFO DISCO
    # ─────────────────────────────────────────
    def _panel_info(self):
        g = QGroupBox("Disco")
        lay = QVBoxLayout()
        lay.setSpacing(4)
        lay.setContentsMargins(10, 6, 10, 6)

        d   = self.disco
        su  = sum(1 for s in d.sectores if s is not None and s.tamano_ocupado > 0)
        cap = d.total_sectores * d.tamano_sector
        bu  = sum(s.tamano_ocupado for s in d.sectores if s is not None)
        pct = (bu / cap * 100) if cap > 0 else 0

        for k, v in [
            ("Geometría", f"{d.platos}P·{d.superficies_por_plato}S·{d.pistas_por_superficie}Pi·{d.sectores_por_pista}Se"),
            ("Sector",    f"{d.tamano_sector} B"),
            ("Total",     f"{d.total_sectores}"),
            ("Usados",    f"{su}"),
            ("Libres",    f"{d.total_sectores - su}"),
        ]:
            r = QHBoxLayout()
            l1 = QLabel(k)
            l1.setStyleSheet(f"color:{T.TXT_D}; font-size:10px;")
            l2 = QLabel(v)
            l2.setStyleSheet(f"color:{T.TXT_W}; font-size:10px; font-weight:600;")
            l2.setAlignment(Qt.AlignmentFlag.AlignRight)
            r.addWidget(l1)
            r.addStretch()
            r.addWidget(l2)
            lay.addLayout(r)

        lay.addWidget(_sep())

        bar_bg = QFrame()
        bar_bg.setFixedHeight(6)
        bar_bg.setStyleSheet(f"background:{T.BG4}; border-radius:3px;")
        bar_fill = QFrame(bar_bg)
        bar_fill.setFixedHeight(6)
        bar_fill.setFixedWidth(max(int(pct * 2.2), 2) if pct > 0 else 0)
        bar_fill.setStyleSheet(f"background:{T.ACC}; border-radius:3px;")
        lay.addWidget(bar_bg)

        ul = QLabel(f"{bu:,}/{cap:,} B ({pct:.1f}%)")
        ul.setStyleSheet(f"color:{T.TXT_D}; font-size:9px;")
        ul.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(ul)

        lay.addWidget(_sep())

        self.lbl_res = QLabel("")
        self.lbl_res.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.lbl_res.setStyleSheet(f"color:{T.ACC};")
        self.lbl_res.setWordWrap(True)
        lay.addWidget(self.lbl_res)

        g.setLayout(lay)
        return g

    # ─────────────────────────────────────────
    #  PANEL: LEYENDA
    # ─────────────────────────────────────────
    def _panel_leyenda(self):
        g = QGroupBox("Leyenda")
        lay = QVBoxLayout()
        lay.setSpacing(6)
        lay.setContentsMargins(10, 6, 10, 6)

        # Disco
        lbl_disco = QLabel("Disco:")
        lbl_disco.setStyleSheet(f"color:{T.TXT_D}; font-size:10px; font-weight:600;")
        lay.addWidget(lbl_disco)
        for c, t in [
            ("#1a2e1a", "Vacío"),
            ("#7a5c10", "Ocupado"),
            ("#2563eb", "Buscado"),
            ("#dc2626", "Compartido"),
        ]:
            r = QHBoxLayout()
            r.setSpacing(8)
            sq = QFrame()
            sq.setFixedSize(14, 14)
            sq.setStyleSheet(f"background:{c}; border:1px solid {T.BORDE}; border-radius:3px;")
            lb = QLabel(t)
            lb.setStyleSheet(f"color:{T.TXT}; font-size:10px;")
            r.addWidget(sq)
            r.addWidget(lb)
            r.addStretch()
            lay.addLayout(r)

        lay.addWidget(_sep())

        # AVL
        lbl_avl = QLabel("Árbol AVL:")
        lbl_avl.setStyleSheet(f"color:{T.TXT_D}; font-size:10px; font-weight:600;")
        lay.addWidget(lbl_avl)
        for c, t in [
            (T.PURPLE, "Raíz"),
            (T.ACC,    "Nodo normal"),
            (T.OK,     "Nodo encontrado"),
        ]:
            r = QHBoxLayout()
            r.setSpacing(8)
            sq = QFrame()
            sq.setFixedSize(14, 14)
            sq.setStyleSheet(f"background:{c}; border-radius:7px;")
            lb = QLabel(t)
            lb.setStyleSheet(f"color:{T.TXT}; font-size:10px;")
            r.addWidget(sq)
            r.addWidget(lb)
            r.addStretch()
            lay.addLayout(r)

        g.setLayout(lay)
        return g

    # ─────────────────────────────────────────
    #  PANEL: DISCO VISUAL
    # ─────────────────────────────────────────
    def _panel_disco(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 6)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)
        for lbl_txt, items, attr in [
            ("Plato",      [str(i) for i in range(self.disco.platos)],               "combo_plato"),
            ("Superficie", [str(i) for i in range(self.disco.superficies_por_plato)], "combo_sup"),
        ]:
            l = QLabel(lbl_txt)
            l.setStyleSheet(f"color:{T.TXT_D}; font-size:10px;")
            cb = QComboBox()
            cb.addItems(items)
            cb.setFixedWidth(55)
            cb.currentIndexChanged.connect(self._upd_disco)
            setattr(self, attr, cb)
            ctrl.addWidget(l)
            ctrl.addWidget(cb)
            ctrl.addSpacing(8)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        self.disco_widget = DiscoWidget(self.disco)
        lay.addWidget(self.disco_widget, stretch=1)
        return w

    # ─────────────────────────────────────────
    #  PANEL: ÁRBOL AVL
    # ─────────────────────────────────────────
    def _panel_avl(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 6)
        lay.setSpacing(6)

        # Controles
        ctrl = QHBoxLayout()
        lbl_col = QLabel("Columna del índice:")
        lbl_col.setStyleSheet(f"color:{T.TXT_D}; font-size:10px;")
        self.avl_col_cb = QComboBox()
        self.avl_col_cb.addItems(self.bd.tablas[self.nombre_tabla]['columnas'])
        self.avl_col_cb.setFixedWidth(120)
        self.avl_col_cb.currentTextChanged.connect(self._upd_avl)

        self.avl_info_lbl = QLabel("")
        self.avl_info_lbl.setStyleSheet(f"color:{T.TXT_D}; font-size:10px;")

        ctrl.addWidget(lbl_col)
        ctrl.addWidget(self.avl_col_cb)
        ctrl.addStretch()
        ctrl.addWidget(self.avl_info_lbl)
        lay.addLayout(ctrl)

        # Canvas en scroll area
        self.avl_canvas = AVLCanvas()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.avl_canvas)
        scroll.setStyleSheet(f"QScrollArea {{ background:{T.BG2}; border:none; }}")
        lay.addWidget(scroll, stretch=1)

        # Recorrido inorden
        self.avl_inorden_lbl = QLabel("")
        self.avl_inorden_lbl.setWordWrap(True)
        self.avl_inorden_lbl.setStyleSheet(
            f"color:{T.TXT_D}; font-size:9px; "
            f"background:{T.BG3}; border-radius:4px; padding:6px;"
        )
        lay.addWidget(self.avl_inorden_lbl)

        return w

    # ─────────────────────────────────────────
    #  PANEL: RESULTADOS
    # ─────────────────────────────────────────
    def _panel_resultados(self):
        g = QGroupBox("Registros")
        lay = QVBoxLayout()
        lay.setContentsMargins(6, 6, 6, 6)

        cols = self.bd.tablas[self.nombre_tabla]['columnas']
        # ── MEJORA: "LBAs" (plural) para mostrar todos los sectores ──
        hdrs = list(cols) + ["CHS (inicio)", "LBAs", "Frags"]

        self.tabla = TablaSmooth()
        self.tabla.setColumnCount(len(hdrs))
        self.tabla.setHorizontalHeaderLabels(hdrs)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.verticalHeader().setDefaultSectionSize(28)
        self.tabla.itemSelectionChanged.connect(self._sel_reg)

        lay.addWidget(self.tabla)
        g.setLayout(lay)
        return g

    # ─────────────────────────────────────────
    #  ACCIONES
    # ─────────────────────────────────────────
    def _upd_disco(self):
        self.disco_widget.set_vista(
            self.combo_plato.currentIndex(),
            self.combo_sup.currentIndex()
        )

    def _upd_avl(self, col=None):
        if col is None:
            col = self.avl_col_cb.currentText()
        tabla = self.bd.tablas[self.nombre_tabla]
        avl   = tabla['indices'].get(col)
        if not avl:
            return
        self.avl_canvas.set_arbol(avl)

        # Info: altura y tamaño
        h  = avl.raiz.altura if avl.raiz else 0
        sz = len(_inorden_claves(avl))
        self.avl_info_lbl.setText(f"Altura: {h}  |  Nodos: {sz}")

        # Recorrido inorden (máx 25 claves para no desbordar)
        claves = _inorden_claves(avl)
        if isinstance(claves[0] if claves else None, float):
            claves_str = [f"{c:.1f}" for c in claves]
        else:
            claves_str = [str(c) for c in claves]
        mostrar = claves_str[:25]
        extra   = len(claves_str) - 25 if len(claves_str) > 25 else 0
        texto   = "Recorrido inorden: " + " → ".join(mostrar)
        if extra > 0:
            texto += f"  … (+{extra} más)"
        self.avl_inorden_lbl.setText(texto)

    def _buscar(self):
        col = self.combo_col.currentText()
        tabla = self.bd.tablas[self.nombre_tabla]
        tipo  = tabla['tipos'].get(col, str)
        avl   = tabla['indices'].get(col)

        if self.radio_exacta.isChecked():
            v = self.inp_val.text().strip()
            if not v:
                QMessageBox.warning(self, "Campo vacío", "Ingrese un valor.")
                return
            res = self.bd.buscar_por_campo(self.nombre_tabla, col, v)
            tit = f"{len(res)} resultado(s) · {col} = '{v}'"
            # Claves a resaltar en el AVL
            try:
                claves_resaltadas = {tipo(v)}
            except (ValueError, TypeError):
                claves_resaltadas = {v}
        else:
            mn = self.inp_min.text().strip()
            mx = self.inp_max.text().strip()
            if not mn or not mx:
                QMessageBox.warning(self, "Campos vacíos", "Ingrese mínimo y máximo.")
                return
            res = self.bd.buscar_por_rango(self.nombre_tabla, col, mn, mx)
            tit = f"{len(res)} resultado(s) · {col} ∈ [{mn}, {mx}]"
            # Claves a resaltar en el AVL
            try:
                min_c = tipo(mn)
                max_c = tipo(mx)
                if min_c > max_c:
                    min_c, max_c = max_c, min_c
                # Mismo ajuste que en buscar_por_rango: en texto, el máximo
                # debe incluir cualquier palabra que empiece con esa letra.
                if tipo is str:
                    max_c = max_c + "\uffff"
                claves_resaltadas = set(_claves_en_rango(avl, min_c, max_c)) if avl else set()
            except (ValueError, TypeError):
                claves_resaltadas = set()

        self.lbl_res.setText(tit)
        self._mostrar(res)

        # ── MEJORA 1: resaltar sectores en el disco ──
        lbas = set()
        for r in res:
            if r["ubicacion"]:
                for lb, _, _ in r["ubicacion"]:
                    lbas.add(lb)
        self.disco_widget.resaltar_sectores(lbas)

        # ── MEJORA 2: auto-switch a plato/superficie del primer resultado ──
        if res and res[0]['ubicacion']:
            lb0  = res[0]['ubicacion'][0][0]
            chs  = self.disco._lba_a_chs(lb0)
            self.combo_plato.setCurrentIndex(chs[0])
            self.combo_sup.setCurrentIndex(chs[1])
            self._upd_disco()

        # ── MEJORA 3: actualizar árbol AVL con la columna buscada ──
        self.avl_col_cb.setCurrentText(col)
        self._upd_avl(col)
        self.avl_canvas.resaltar(claves_resaltadas)

        # Cambiar a la pestaña del árbol si tiene resultados
        # (opcional: descomenta la siguiente línea si quieres auto-saltar al árbol)
        # if res: self.tabs.setCurrentIndex(1)

    def _limpiar(self):
        self.inp_val.clear()
        self.inp_min.clear()
        self.inp_max.clear()
        self.lbl_res.setText("")
        self.disco_widget.limpiar_resaltado()
        self.avl_canvas.limpiar()
        self._mostrar(self.bd.listar_registros(self.nombre_tabla))

    def _mostrar(self, resultados):
        cols = self.bd.tablas[self.nombre_tabla]['columnas']
        self.tabla.setRowCount(len(resultados))
        self._res = resultados

        for i, r in enumerate(resultados):
            # Columnas de datos
            for j, c in enumerate(cols):
                it = QTableWidgetItem(str(r["registro"].get(c, "")))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(i, j, it)

            if r["ubicacion"]:
                lb0 = r["ubicacion"][0][0]
                chs = self.disco._lba_a_chs(lb0)
                cs  = f"P{chs[0]} S{chs[1]} Pi{chs[2]} Se{chs[3]}"
                # ── MEJORA: mostrar TODOS los LBAs ──
                todos_lba = ", ".join(str(ub[0]) for ub in r["ubicacion"])
                fs  = str(len(r["ubicacion"]))
            else:
                cs, todos_lba, fs = "—", "—", "—"

            for j, v in enumerate([cs, todos_lba, fs], len(cols)):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(i, j, it)

        self.tabla.resizeColumnsToContents()

    def _sel_reg(self):
        fi = self.tabla.selectionModel().selectedRows()
        if not fi or not hasattr(self, '_res'):
            return
        idx = fi[0].row()
        if idx >= len(self._res):
            return
        r    = self._res[idx]
        lbas = set()
        if r["ubicacion"]:
            for lb, _, _ in r["ubicacion"]:
                lbas.add(lb)
        self.disco_widget.resaltar_sectores(lbas)

        # ── Auto-switch al plato/superficie del registro seleccionado ──
        if r["ubicacion"]:
            lb0 = r["ubicacion"][0][0]
            chs = self.disco._lba_a_chs(lb0)
            self.combo_plato.setCurrentIndex(chs[0])
            self.combo_sup.setCurrentIndex(chs[1])
            self._upd_disco()

    def showEvent(self, event):
        super().showEvent(event)
        res = self.bd.listar_registros(self.nombre_tabla)
        self._mostrar(res)
        self.lbl_res.setText(f"{len(res)} registros cargados")
        # Cargar el AVL con la primera columna al arrancar
        self._upd_avl(self.avl_col_cb.currentText())