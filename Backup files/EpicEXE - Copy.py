import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QLabel, QMenu, QMessageBox, QPlainTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon

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

class PatchTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EpicEXE - ROM Feature Patcher")
        self.setWindowIcon(QIcon("epic_icon.ico"))
        self.resize(750, 600)

        self.rom_path = None
        self.features = []

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

        self.detail_text = QPlainTextEdit()
        self.detail_text.setFont(QFont("Courier New", 10))
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet("""
            QPlainTextEdit {
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

        for line in lines:
            if line.startswith("[") and line.endswith("]"):
                if current_feature["patches"]:
                    self.features.append(current_feature)
                    self.add_feature_item(len(self.features) - 1)
                section_title = line[1:-1]
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
                    if "offset" in current_feature:
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

        if "offset" in current_feature and "original" in current_feature and "modified" in current_feature:
            current_feature["patches"].append({
                "offset": current_feature.pop("offset"),
                "original": current_feature.pop("original"),
                "modified": current_feature.pop("modified")
            })
        if current_feature["patches"]:
            self.features.append(current_feature)
            self.add_feature_item(len(self.features) - 1)

    def add_feature_item(self, index):
        feature = self.features[index]
        statuses = []
        for patch in feature["patches"]:
            try:
                current = read_rom_bytes(self.rom_path, patch["offset"], len(patch["modified"]))
                if current == patch["modified"]:
                    statuses.append("✅ mod")
                elif current == patch["original"]:
                    statuses.append("🔄 og")
                else:
                    statuses.append("⚠️ unk")
            except Exception:
                statuses.append("❌")
        status = max(set(statuses), key=statuses.count)
        display_line = f"📛 {feature['name']} – {feature['description']} [{status}]"
        item = QListWidgetItem(display_line)
        item.setFont(QFont("Consolas", 10))
        item.setData(Qt.UserRole, index)
        self.feature_list.addItem(item)

    def update_bottom_panel_from_list(self, item):
        index = item.data(Qt.UserRole)
        self.update_bottom_panel(index)

    def update_bottom_panel(self, index):
        if index >= len(self.features):
            return
        feature = self.features[index]
        text = f"📛 Feature: {feature['name']}\n📝 Description: {feature['description']}\n"
        for i, patch in enumerate(feature["patches"]):
            try:
                current = read_rom_bytes(self.rom_path, patch["offset"], len(patch["modified"]))
                orig = format_bytes(patch["original"])
                mod = format_bytes(patch["modified"])
                exe = format_bytes(current)
                text += (
                    f"\n🧮 Patch {i + 1}\n"
                    f"Offset: 0x{patch['offset']:06X}\n"
                    f"Original:   {orig}\n"
                    f"Modified:   {mod}\n"
                    f"Executable: {exe}\n"
                )
            except Exception as e:
                text += f"\n⚠️ Patch {i + 1} read error: {e}\n"
        self.detail_text.setPlainText(text)

    def show_context_menu(self, pos):
        item = self.feature_list.itemAt(pos)
        if not item:
            return

        index = item.data(Qt.UserRole)
        feature = self.features[index]

        menu = QMenu()
        mod_action = menu.addAction("Set All Modified")
        orig_action = menu.addAction("Set All Original")

        action = menu.exec_(self.feature_list.viewport().mapToGlobal(pos))

        if action == mod_action:
            for patch in feature["patches"]:
                write_rom_bytes(self.rom_path, patch["offset"], patch["modified"])
        elif action == orig_action:
            for patch in feature["patches"]:
                write_rom_bytes(self.rom_path, patch["offset"], patch["original"])

        self.add_feature_item(index)  # Refresh status
        self.update_bottom_panel(index)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PatchTool()
    window.show()
    sys.exit(app.exec_())
