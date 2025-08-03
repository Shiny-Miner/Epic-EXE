import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QLabel, QMenu, QMessageBox, QPlainTextEdit, QTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
import json


def except_hook(cls, exception, traceback):
    with open("error.log", "w") as f:
        f.write(f"Unhandled Exception:\n{cls.__name__}: {exception}")
    sys.__excepthook__(cls, exception, traceback)

sys.excepthook = except_hook

def hex_to_bytes(hex_str):
    return bytes(int(b, 16) for b in hex_str.strip().split())

def read_rom_bytes(rom_path, offset, length):
    with open(rom_path, 'rb') as f:
        f.seek(offset)
        return f.read(length)

def write_rom_bytes(rom_path, offset, data):
    with open(rom_path, 'rb+') as f:
        f.seek(offset)
        f.write(data)

def format_bytes(data):
    return ' '.join(f"{b:02X}" for b in data)

import sys, os
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

def resource_path(relative_path):
    """ Get absolute path to resource, works for .py and .exe """
    if hasattr(sys, '_MEIPASS'):  # Running in PyInstaller bundle
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class PatchTool(QWidget):
    def __init__(self):
        super().__init__()

        # --- Windows taskbar icon fix ---
        if sys.platform.startswith("win"):
            import ctypes
            myappid = 'EpicEXE.App'  # arbitrary unique ID
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        # --- Title bar + taskbar icon ---
        self.setWindowTitle("EpicEXE - ROM Feature Patcher")
        self.setWindowIcon(QIcon(resource_path("exe_icon.ico")))
        self.resize(750, 600)

        self.rom_path = None
        self.features = []
        self.original_feature_state = {}  # {feature_index: [(offset, bytes), ...]}

        layout = QVBoxLayout()

        self.load_rom_btn = QPushButton("Load ROM")
        self.load_ini_btn = QPushButton("Load .ini File")

        for btn in [self.load_rom_btn, self.load_ini_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3C3C3C;
                    color: #FFFFFF;
                    padding: 8px;
                    font-size: 14px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
            """)

        self.load_rom_btn.clicked.connect(self.load_rom)
        self.load_ini_btn.clicked.connect(self.load_ini)

        layout.addWidget(self.load_rom_btn)
        layout.addWidget(self.load_ini_btn)

        self.feature_list = QListWidget()
        self.feature_list.setFont(QFont("Consolas", 10))
        self.feature_list.setMaximumHeight(250)
        self.feature_list.setStyleSheet("""
            QListWidget {
                font-size: 12px;
                background-color: #2A2A2A;
                color: #FFFFFF;
            }
            QListWidget::item {
                padding: 6px;
            }
        """)

        self.feature_list.itemClicked.connect(self.update_bottom_panel_from_list)
        self.feature_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.feature_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.feature_list)

        self.detail_text = QTextEdit()
        self.detail_text.setFont(QFont("Courier New", 10))
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                padding: 10px;
                border: 1px solid #DDD;
            }
        """)

        layout.addWidget(self.detail_text)

        self.setLayout(layout)
        self.setStyleSheet(self.styleSheet() + """
            QWidget {
                background-color: #1E1E1E;
            }
        """)

    def load_rom(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select ROM", "", "GBA ROMs (*.gba)")
        if path:
            self.rom_path = path
            self.setWindowTitle(f"EpicEXE - {os.path.basename(path)}")

            # Original state file name for this ROM
            self.state_filename = f"epicexe_original_{os.path.basename(path)}.json"

            # Load previous original state if available
            if os.path.exists(self.state_filename):
                with open(self.state_filename, "r") as f:
                    raw = json.load(f)
                self.original_feature_state = {
                    int(k): [(off, bytes.fromhex(data)) for off, data in v]
                    for k, v in raw.items()
                }
            else:
                self.original_feature_state = {}


    def load_ini(self):
        if not self.rom_path:
            QMessageBox.warning(self, "Error", "Please load a ROM first.")
            return

        path, _ = QFileDialog.getOpenFileName(self, "Select INI File", "", "INI Files (*.ini)")
        if not path:
            return

        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        self.features = []
        self.feature_list.clear()

        section_title = None
        current_feature = {"patches": []}
        feature_index = -1  # Track current feature index

        for line in lines:
            if line.startswith("[") and line.endswith("]"):
                if current_feature["patches"]:
                    self.features.append(current_feature)
                    self.add_feature_item(len(self.features) - 1)

                section_title = line[1:-1]
                feature_index = len(self.features)  # index before adding
                current_feature = {"name": f"Feature {section_title}", "description": "", "patches": []}
                continue

            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip().lower()
                val = val.strip()

                if key == "name":
                    current_feature["name"] = val
                elif key in ("description", "hackdescription"):
                    current_feature["description"] = val
                elif key == "offset":
                    if all(k in current_feature for k in ("offset", "original", "modified")):
                        current_feature["patches"].append({
                            "offset": current_feature.pop("offset"),
                            "original": current_feature.pop("original"),
                            "modified": current_feature.pop("modified")
                        })
                    current_feature["offset"] = int(val, 16)
                elif key == "original":
                    current_feature["original"] = hex_to_bytes(val)
                elif key == "modified":
                    current_feature["modified"] = hex_to_bytes(val)

                    # Capture original bytes for "Set All Unknown" if not stored yet
                    try:
                        off = current_feature["offset"]
                        length = len(current_feature["modified"])
                        if feature_index not in self.original_feature_state:
                            self.original_feature_state[feature_index] = []
                        if not any(o == off for o, _ in self.original_feature_state[feature_index]):
                            current_bytes = read_rom_bytes(self.rom_path, off, length)
                            self.original_feature_state[feature_index].append((off, current_bytes))
                    except Exception:
                        pass

        # Append last patch if complete
        if all(k in current_feature for k in ("offset", "original", "modified")):
            current_feature["patches"].append({
                "offset": current_feature.pop("offset"),
                "original": current_feature.pop("original"),
                "modified": current_feature.pop("modified")
            })

        if current_feature["patches"]:
            self.features.append(current_feature)
            self.add_feature_item(len(self.features) - 1)

        # Save original state to file if it doesn't exist
        if not os.path.exists(self.state_filename):
            save_data = {
                str(k): [(off, data.hex()) for off, data in v]
                for k, v in self.original_feature_state.items()
            }
            with open(self.state_filename, "w") as f:
                json.dump(save_data, f, indent=2)


    def add_feature_item(self, index):
        feature = self.features[index]
        statuses = []
        for patch in feature["patches"]:
            try:
                current = read_rom_bytes(self.rom_path, patch["offset"], len(patch["modified"]))
                if current == patch["modified"]:
                    statuses.append("mod")
                elif current == patch["original"]:
                    statuses.append("og")
                else:
                    statuses.append("unk")
            except Exception:
                statuses.append("err")

        status = max(set(statuses), key=statuses.count)
        display_line = f"📛 {feature['name']} – {feature['description']} [{status}]"
        item = QListWidgetItem(display_line)
        item.setFont(QFont("Consolas", 10))
        item.setData(Qt.UserRole, index)

        # Color mapping
        if status == "mod":
            item.setForeground(Qt.green)
        elif status == "unk":
            item.setForeground(Qt.red)
        else:  # original or err
            item.setForeground(Qt.white)

        self.feature_list.addItem(item)

    def update_bottom_panel_from_list(self, item):
        index = item.data(Qt.UserRole)
        self.update_bottom_panel(index)

    def update_bottom_panel(self, index):
        if index >= len(self.features):
            return
        feature = self.features[index]
        html = f"<b>📛 Feature:</b> {feature['name']}<br><b>📝 Description:</b> {feature['description']}<br>"

        for i, patch in enumerate(feature["patches"]):
            try:
                current = read_rom_bytes(self.rom_path, patch["offset"], len(patch["modified"]))
                orig = format_bytes(patch["original"])
                mod = format_bytes(patch["modified"])
                exe = format_bytes(current)

                # Determine executable color
                if current == patch["modified"]:
                    exe_color = "#00FF00"  # green
                elif current == patch["original"]:
                    exe_color = "#FFFFFF"  # white
                else:
                    exe_color = "#FF0000"  # red

                html += (
                    f"<br><b>🧮 Patch {i + 1}</b><br>"
                    f"Offset: 0x{patch['offset']:06X}<br>"
                    f"Original:   {orig}<br>"
                    f"Modified:   {mod}<br>"
                    f"<span style='color:{exe_color}'>Executable: {exe}</span><br>"
                )
            except Exception as e:
                html += f"<br>⚠️ Patch {i + 1} read error: {e}<br>"

        self.detail_text.setHtml(html)


    def show_context_menu(self, pos):
        item = self.feature_list.itemAt(pos)
        if not item:
            return

        index = item.data(Qt.UserRole)
        feature = self.features[index]

        menu = QMenu()
        mod_action = menu.addAction("Set All Modified")
        orig_action = menu.addAction("Set All Original")
        unk_action = menu.addAction("Set All Unknown")  # New option

        action = menu.exec_(self.feature_list.viewport().mapToGlobal(pos))

        if action == mod_action:
            for patch in feature["patches"]:
                write_rom_bytes(self.rom_path, patch["offset"], patch["modified"])
        elif action == orig_action:
            for patch in feature["patches"]:
                write_rom_bytes(self.rom_path, patch["offset"], patch["original"])
        elif action == unk_action:
            if index in self.original_feature_state:
                for off, data in self.original_feature_state[index]:
                    write_rom_bytes(self.rom_path, off, data)

        # Refresh full list and details
        self.feature_list.clear()
        for i in range(len(self.features)):
            self.add_feature_item(i)
        self.update_bottom_panel(index)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PatchTool()
    window.show()
    sys.exit(app.exec_())
