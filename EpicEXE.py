import sys
import os
import configparser
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QLabel, QMenu, QMessageBox
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
            btn.setStyleSheet("padding: 8px; font-size: 14px; border-radius: 6px;")

        self.load_rom_btn.clicked.connect(self.load_rom)
        self.load_ini_btn.clicked.connect(self.load_ini)

        layout.addWidget(self.load_rom_btn)
        layout.addWidget(self.load_ini_btn)

        self.feature_list = QListWidget()
        self.feature_list.setFont(QFont("Consolas", 10))
        self.feature_list.setStyleSheet("""
            QListWidget::item { padding: 6px; }
            QListWidget { font-size: 12px; }
        """)
        self.feature_list.itemClicked.connect(self.update_bottom_panel_from_list)
        self.feature_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.feature_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.feature_list)

        self.detail_text = QLabel("Select a feature to see full info below.")
        self.detail_text.setFont(QFont("Courier New", 10))
        self.detail_text.setStyleSheet("""
            QLabel {
                background-color: #F5F5F5;
                padding: 10px;
                border: 1px solid #DDD;
            }
        """)
        self.detail_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.detail_text)

        self.setLayout(layout)

        # Background color
        self.setStyleSheet(self.styleSheet() + """
            QWidget {
                background-color: #FAFAFC;
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

        config = configparser.ConfigParser()
        config.read(path)

        self.features = []
        self.feature_list.clear()

        for section in config.sections():
            try:
                desc = config[section].get("description", "")
                offset = int(config[section]["offset"], 16)
                original = hex_to_bytes(config[section]["original"])
                modified = hex_to_bytes(config[section]["modified"])
                current = read_rom_bytes(self.rom_path, offset, len(modified))

                status = "✅ Modified" if current == modified else "🔄 Original" if current == original else "⚠️ Unknown"
                display_line = f"📛 {section} – {desc} [{status}]"

                self.features.append({
                    "name": section,
                    "description": desc,
                    "offset": offset,
                    "original": original,
                    "modified": modified
                })

                item = QListWidgetItem(display_line)
                item.setFont(QFont("Consolas", 10))
                item.setData(Qt.UserRole, len(self.features) - 1)
                self.feature_list.addItem(item)
            except Exception as e:
                QMessageBox.critical(self, "INI Parse Error", f"Feature '{section}' is invalid:\n{e}")

    def update_bottom_panel_from_list(self, item):
        index = item.data(Qt.UserRole)
        self.update_bottom_panel(index)

    def update_bottom_panel(self, index):
        if index >= len(self.features):
            return
        feature = self.features[index]
        try:
            current = read_rom_bytes(self.rom_path, feature["offset"], len(feature["modified"]))
            name = feature["name"]
            desc = feature["description"]
            offset = feature["offset"]
            orig = format_bytes(feature["original"])
            mod = format_bytes(feature["modified"])
            exe = format_bytes(current)

            self.detail_text.setText(
                f"📛 Feature: {name}\n"
                f"📝 Description: {desc}\n"
                f"🧮 Offset: 0x{offset:06X}\n\n"
                f"🧾 Original:   {orig}\n"
                f"🧾 Modified:   {mod}\n"
                f"🧾 Executable: {exe}"
            )

        except Exception as e:
            self.detail_text.setText(f"⚠️ Error reading feature: {e}")

    def show_context_menu(self, pos):
        item = self.feature_list.itemAt(pos)
        if not item:
            return

        index = item.data(Qt.UserRole)
        feature = self.features[index]

        menu = QMenu()
        mod_action = menu.addAction("Set Modified")
        orig_action = menu.addAction("Set Original")

        action = menu.exec_(self.feature_list.viewport().mapToGlobal(pos))

        if action == mod_action:
            write_rom_bytes(self.rom_path, feature["offset"], feature["modified"])
        elif action == orig_action:
            write_rom_bytes(self.rom_path, feature["offset"], feature["original"])

        # Refresh status line manually
        current = read_rom_bytes(self.rom_path, feature["offset"], len(feature["modified"]))
        status = "✅ Modified" if current == feature["modified"] else "🔄 Original" if current == feature["original"] else "⚠️ Unknown"
        display_line = f"📛 {feature['name']} – {feature['description']} [{status}]"
        self.feature_list.item(index).setText(display_line)
        self.update_bottom_panel(index)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PatchTool()
    window.show()
    sys.exit(app.exec_())
