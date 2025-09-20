from PyQt5.QtGui import QPixmap
import sys
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLineEdit, QLabel,
    QComboBox, QFileDialog, QMessageBox, QHeaderView, QDialog, QFrame,
    QCompleter, QStyledItemDelegate
)
from PyQt5.QtCore import Qt, QStringListModel, QEvent
from PyQt5.QtGui import QIntValidator, QKeyEvent
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from datetime import datetime
import os
import webbrowser
import pickle

# ============== Custom delegate for On Hand column (numeric + enter/down) ==============
class OnHandDelegate(QStyledItemDelegate):
    """Numeric-only editor; Enter moves to next row; Backspace works naturally."""
    def __init__(self, table, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table = table  # reference to QTableWidget

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setValidator(QIntValidator(0, 10**9, editor))
        editor.setAlignment(Qt.AlignCenter)
        editor.installEventFilter(self)  # so eventFilter gets key presses
        return editor

    def eventFilter(self, editor, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()

            # ENTER: commit edit and move to next row same column; keep editing
            if key in (Qt.Key_Return, Qt.Key_Enter):
                # Commit & close the inline editor
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)

                row = self.table.currentRow()
                col = self.table.currentColumn()  # should be 4 (On Hand)
                next_row = row + 1
                if next_row < self.table.rowCount():
                    self.table.setCurrentCell(next_row, col)
                    # start editing next cell immediately
                    item = self.table.item(next_row, col)
                    if item is None:
                        item = QTableWidgetItem("")
                        item.setTextAlignment(Qt.AlignCenter)
                        self.table.setItem(next_row, col, item)
                    self.table.editItem(item)
                return True

            # Let QLineEdit handle Backspace normally; no special case needed here.
        return super().eventFilter(editor, event)

# ========================= Invoice dialog (read-only) =======================
class InvoiceDialog(QDialog):
    def __init__(self, vendor_name, branch, invoice_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Invoice")
        self.setModal(True)

        self.vendor_name = vendor_name
        self.branch = branch
        self.invoice_data = invoice_data

        layout = QVBoxLayout(self)

        # Header
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Box)
        header_layout = QVBoxLayout(header_frame)

        title_label = QLabel("VENDOR DEMAND INVOICE")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 5px; color: darkblue;")
        header_layout.addWidget(title_label)

        for txt, fs in [
            (f"Vendor: {vendor_name}", 12),
            (f"Branch: {branch}", 12),
            (f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 11),
        ]:
            lb = QLabel(txt)
            lb.setAlignment(Qt.AlignCenter)
            lb.setStyleSheet(f"font-size: {fs}px; margin: 2px; color: black;")
            header_layout.addWidget(lb)

        layout.addWidget(header_frame)

        # Items (READ-ONLY)
        items_frame = QFrame()
        items_layout = QVBoxLayout(items_frame)

        items_label = QLabel("ITEMS DETAILS")
        items_label.setAlignment(Qt.AlignCenter)
        items_label.setStyleSheet("font-size: 13px; font-weight: bold; margin: 5px;")
        items_layout.addWidget(items_label)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Item Name", "Order Qty"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.table.setRowCount(len(invoice_data))
        for row, (product, qty) in enumerate(invoice_data):
            try:
                q = int(float(qty)) if str(qty).strip() else 0
            except:
                q = 0
            name_item = QTableWidgetItem(str(product))
            qty_item = QTableWidgetItem(str(q))
            for it in (name_item, qty_item):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, qty_item)

        items_layout.addWidget(self.table)
        layout.addWidget(items_frame)

        # Buttons
        buttons_layout = QHBoxLayout()

        print_btn = QPushButton("Print")
        print_btn.clicked.connect(self.print_invoice)
        print_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 6px; font-weight: bold; }")
        buttons_layout.addWidget(print_btn)

        whatsapp_btn = QPushButton("WhatsApp")
        whatsapp_btn.clicked.connect(self.share_via_whatsapp)
        whatsapp_btn.setStyleSheet("QPushButton { background-color: #25D366; color: white; padding: 6px; font-weight: bold; }")
        buttons_layout.addWidget(whatsapp_btn)

        screenshot_btn = QPushButton("Screenshot")
        screenshot_btn.clicked.connect(self.capture_screenshot)
        screenshot_btn.setStyleSheet("QPushButton { background-color: #9C27B0; color: white; padding: 6px; font-weight: bold; }")
        buttons_layout.addWidget(screenshot_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("QPushButton { background-color: #F44336; color: white; padding: 6px; font-weight: bold; }")
        buttons_layout.addWidget(close_btn)

        layout.addLayout(buttons_layout)

        # ---- Size & Positioning ----
        self.adjustSize()  # shrink to fit content
        self.resize(400, 500)  # enforce smaller size

        if parent:
            geo = parent.frameGeometry()
            center = geo.center()
            # move dialog a bit above center (like “from neck”)
            self.move(center.x() - self.width() // 2,
                      center.y() - self.height() // 2 - 100)

    def print_invoice(self):
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec_() == QPrintDialog.Accepted:
            QMessageBox.information(self, "Print", "Invoice sent to printer!")

    def share_via_whatsapp(self):
        lines = [
            "*Vendor Demand Invoice*",
            f"*Vendor:* {self.vendor_name}",
            f"*Branch:* {self.branch}",
            f"*Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "*ITEMS:*",
        ]
        total = 0
        for product, qty in self.invoice_data:
            try:
                q = int(float(qty)) if str(qty).strip() else 0
            except:
                q = 0
            total += q
            lines.append(f"- {product}: {q}")
        lines += ["", f"*TOTAL ITEMS:* {len(self.invoice_data)}", f"*TOTAL QTY:* {total}"]

        import urllib.parse
        url = "https://wa.me/?text=" + urllib.parse.quote("\n".join(lines))
        # reuse existing tab if open
        webbrowser.open(url, new=0)

    def capture_screenshot(self):
        # Render full invoice dialog contents into a pixmap
        full_size = self.sizeHint()
        pixmap = QPixmap(full_size)
        self.render(pixmap)

        # Copy to clipboard only (no saving to file)
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(pixmap)

        QMessageBox.information(
            self,
            "Screenshot",
            "Invoice screenshot copied to clipboard.\n\n"
            "Open WhatsApp and press Ctrl+V to paste."
    )

    def print_invoice(self):
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec_() == QPrintDialog.Accepted:
            QMessageBox.information(self, "Print", "Invoice sent to printer!")

    def share_via_whatsapp(self):
        lines = [
            "*Vendor Demand Invoice*",
            f"*Vendor:* {self.vendor_name}",
            f"*Branch:* {self.branch}",
            f"*Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "*ITEMS:*",
        ]
        total = 0
        for product, qty in self.invoice_data:
            try:
                q = int(float(qty)) if str(qty).strip() else 0
            except:
                q = 0
            total += q
            lines.append(f"- {product}: {q}")
        lines += ["", f"*TOTAL ITEMS:* {len(self.invoice_data)}", f"*TOTAL QTY:* {total}"]

        import urllib.parse
        url = "https://wa.me/?text=" + urllib.parse.quote("\n".join(lines))
        webbrowser.open(url)

# ============================== Main Window ==============================
class VendorDemandApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vendor Demand Forecasting System")
        self.setGeometry(100, 100, 1200, 800)

        # Data
        self.vendor_data = {}   # {vendor: [[name, base1, base2, base5], ...]}
        self.current_vendor = None
        self.branch_names = ["Shahbaz", "Clifton", "BHD"]
        self.data_file = "vendor_data.pkl"

        # UI/State helpers
        self._signal_guard = False
        self.proj_col_idx = -1             # single dynamic projection column index; -1 = none
        self.current_projection = None     # "1", "2", or "5"
        self.vendor_list_model = QStringListModel([])

        self._load_vendor_data_from_file()
        self._init_ui()
        self._update_button_states()

    # ---------------- Persistence ----------------
    def _load_vendor_data_from_file(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "rb") as f:
                    self.vendor_data = pickle.load(f)
        except Exception as e:
            print("Failed to load saved vendor data:", e)

    def _save_vendor_data_to_file(self):
        try:
            with open(self.data_file, "wb") as f:
                pickle.dump(self.vendor_data, f)
        except Exception as e:
            print("Failed to save vendor data:", e)

    # ---------------- UI ----------------
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Import row
        import_layout = QHBoxLayout()
        self.import_btn = QPushButton("Import Excel File")
        self.import_btn.clicked.connect(self.import_excel)
        self.import_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; }")
        import_layout.addWidget(self.import_btn)

        self.load_new_btn = QPushButton("Load New Excel File")
        self.load_new_btn.clicked.connect(self.load_new_excel)
        self.load_new_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 10px; }")
        self.load_new_btn.setVisible(bool(self.vendor_data))
        import_layout.addWidget(self.load_new_btn)

        import_layout.addStretch()
        main_layout.addLayout(import_layout)

        # Status
        self.status_label = QLabel("No data loaded" if not self.vendor_data else f"Data loaded for {len(self.vendor_data)} vendors")
        main_layout.addWidget(self.status_label)

        # Search + completer
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Vendor:"))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type vendor name")
        search_layout.addWidget(self.search_input)

        self.completer = QCompleter(self.vendor_list_model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.search_input.setCompleter(self.completer)
        self.search_input.returnPressed.connect(self.search_vendor)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search_vendor)
        self.search_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px; }")
        search_layout.addWidget(self.search_btn)

        search_layout.addWidget(QLabel("Branch:"))
        self.branch_combo = QComboBox()
        self.branch_combo.addItems(self.branch_names)
        search_layout.addWidget(self.branch_combo)

        main_layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Product Name", "1 Day Projection", "2 Days Projection", "5 Days Projection", "On Hand"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # APPLY custom delegate for On Hand column
        self.table.setItemDelegateForColumn(4, OnHandDelegate(self.table))

        main_layout.addWidget(self.table)

        # Buttons
        buttons_layout = QHBoxLayout()
        self.day1_btn = QPushButton("1 Day Projection")
        self.day2_btn = QPushButton("2 Days Projection")
        self.day5_btn = QPushButton("5 Days Projection")
        self.save_btn = QPushButton("Save Invoice")
        self.cancel_btn = QPushButton("Cancel")

        for b in (self.day1_btn, self.day2_btn, self.day5_btn):
            b.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 10px; font-weight: bold; }")
        self.save_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; padding: 10px; font-weight: bold; }")
        self.cancel_btn.setStyleSheet("QPushButton { background-color: #F44336; color: white; padding: 10px; font-weight: bold; }")

        self.day1_btn.clicked.connect(lambda: self.create_or_update_projection("1"))
        self.day2_btn.clicked.connect(lambda: self.create_or_update_projection("2"))
        self.day5_btn.clicked.connect(lambda: self.create_or_update_projection("5"))
        self.save_btn.clicked.connect(self.save_invoice)
        self.cancel_btn.clicked.connect(self.cancel_records)

        buttons_layout.addWidget(self.day1_btn)
        buttons_layout.addWidget(self.day2_btn)
        buttons_layout.addWidget(self.day5_btn)
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(buttons_layout)

        # Recalc when On Hand changes
        self.table.cellChanged.connect(self._on_cell_changed)

        # Completer list init
        self._refresh_completer()

    # -------- Key handling at table level (Backspace when not editing) --------
    def keyPressEvent(self, event: QKeyEvent):
        """
        If table has focus and user presses Backspace while NOT editing,
        clear current On Hand cell text.
        """
        if self.table.hasFocus():
            current = self.table.currentItem()
            if current and current.column() == 4:
                if event.key() == Qt.Key_Backspace:
                    # If not in edit mode, clear the cell
                    if not self.table.state() == self.table.EditingState:
                        self._signal_guard = True
                        current.setText("")
                        self._signal_guard = False
                        return
        super().keyPressEvent(event)

    def _refresh_completer(self):
        self.vendor_list_model.setStringList(sorted(self.vendor_data.keys()))

    def _update_button_states(self):
        has_data = bool(self.vendor_data)
        has_vendor = self.current_vendor is not None
        self.search_btn.setEnabled(has_data)
        for b in (self.day1_btn, self.day2_btn, self.day5_btn, self.save_btn, self.cancel_btn):
            b.setEnabled(has_vendor)

    # ---------------- Import / Load ----------------
    def import_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx *.xls)")
        if not file_path:
            return
        try:
            excel_file = pd.ExcelFile(file_path)
            new_data = {}
            for sheet in excel_file.sheet_names:
                vendor = sheet
                raw = pd.read_excel(excel_file, sheet_name=sheet, header=None).iloc[:, :4]
                rows = []
                for _, r in raw.iterrows():
                    name = str(r.iloc[0]) if not pd.isna(r.iloc[0]) else ""
                    p1 = float(r.iloc[1]) if not pd.isna(r.iloc[1]) else 0.0
                    p2 = float(r.iloc[2]) if not pd.isna(r.iloc[2]) else 0.0
                    p3 = float(r.iloc[3]) if not pd.isna(r.iloc[3]) else 0.0
                    if name.strip():
                        rows.append([name, p1, p2, p3])
                new_data[vendor] = rows

            self.vendor_data = new_data
            self._save_vendor_data_to_file()
            self.status_label.setText(f"Data loaded for {len(self.vendor_data)} vendors")
            self.load_new_btn.setVisible(True)
            self._refresh_completer()
            self._update_button_states()
            QMessageBox.information(self, "Success", f"Imported {len(self.vendor_data)} vendors")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def load_new_excel(self):
        self.vendor_data = {}
        self.current_vendor = None
        self.table.setRowCount(0)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Product Name", "1 Day Projection", "2 Days Projection", "5 Days Projection", "On Hand"]
        )
        self.table.setItemDelegateForColumn(4, OnHandDelegate(self.table))
        self.search_input.clear()
        self.status_label.setText("No data loaded")
        self.load_new_btn.setVisible(False)
        self.proj_col_idx = -1
        self.current_projection = None
        self._refresh_completer()
        self._update_button_states()
        if os.path.exists(self.data_file):
            os.remove(self.data_file)
        self.import_excel()

    # ---------------- Search ----------------
    def search_vendor(self):
        vendor_name = self.search_input.text().strip()
        if not vendor_name:
            return
        q = vendor_name.lower()
        matches = [v for v in self.vendor_data.keys() if q in v.lower()]
        if not matches:
            QMessageBox.warning(self, "Warning", f"No vendor '{vendor_name}' found")
            return
        self.current_vendor = matches[0]
        self.load_vendor_data()
        self._update_button_states()

    def load_vendor_data(self):
        # Reset table to base 5 columns & clear projection column
        self._signal_guard = True
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Product Name", "1 Day Projection", "2 Days Projection", "5 Days Projection", "On Hand"]
        )
        self.table.setItemDelegateForColumn(4, OnHandDelegate(self.table))
        self.proj_col_idx = -1
        self.current_projection = None
        self._signal_guard = False

        data = self.vendor_data.get(self.current_vendor, [])
        self.table.setRowCount(len(data))
        for r, row_data in enumerate(data):
            name, p1, p2, p3 = row_data

            name_item = QTableWidgetItem(str(name))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 0, name_item)

            for ci, val in zip((1, 2, 3), (p1, p2, p3)):
                it = QTableWidgetItem(str(int(round(val))))
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, ci, it)

            on_item = QTableWidgetItem("")
            on_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 4, on_item)

    # ---------------- Single projection column logic ----------------
    def _validate_any_on_hand_filled(self):
        """Return True if at least one On Hand cell has a number > 0; else warn and return False."""
        any_filled = False
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 4)
            if it and it.text().strip():
                try:
                    val = int(it.text())
                except:
                    QMessageBox.warning(self, "Invalid On Hand", "Only numbers are allowed in On Hand.")
                    return False
                if val > 0:
                    any_filled = True
        if not any_filled:
            QMessageBox.warning(self, "Missing On Hand", "Please enter On Hand for at least one item before creating a projection.")
            return False
        return True

    def create_or_update_projection(self, which: str):
        """
        which: "1", "2", or "5" meaning base column index 1, 2, or 3 respectively.
        Ensures exactly one dynamic projection column exists, placed right after On Hand.
        """
        if not self.current_vendor:
            return

        if not self._validate_any_on_hand_filled():
            return

        header_text = {"1": "1 Day Projection", "2": "2 Days Projection", "5": "5 Days Projection"}[which]
        base_col_idx = {"1": 1, "2": 2, "5": 3}[which]

        insert_pos = 5  # after On Hand
        self._signal_guard = True

        if self.proj_col_idx == -1:
            self.table.insertColumn(insert_pos)
            self.proj_col_idx = insert_pos
        elif self.proj_col_idx != insert_pos:
            self.table.removeColumn(self.proj_col_idx)
            self.table.insertColumn(insert_pos)
            self.proj_col_idx = insert_pos

        self.table.setHorizontalHeaderItem(self.proj_col_idx, QTableWidgetItem(header_text))

        # Fill projection values
        for r in range(self.table.rowCount()):
            try:
                base_val = float(self.table.item(r, base_col_idx).text())
            except:
                base_val = 0.0
            try:
                on_val = float(self.table.item(r, 4).text())
            except:
                on_val = 0.0
            val = max(0, int(round(base_val - on_val)))
            it = QTableWidgetItem(str(val))
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, self.proj_col_idx, it)

        self.current_projection = which
        self._signal_guard = False

    def _on_cell_changed(self, row, col):
        # Only respond to On Hand edits and only if projection column exists
        if self._signal_guard or col != 4 or self.proj_col_idx == -1 or self.current_projection is None:
            return

        # normalize On Hand to int
        it = self.table.item(row, 4)
        try:
            val = int(it.text()) if it and it.text().strip() else 0
        except:
            val = 0
        self._signal_guard = True
        self.table.item(row, 4).setText(str(val))
        self._signal_guard = False

        # Recompute this row for the current projection type
        base_col_idx = {"1": 1, "2": 2, "5": 3}[self.current_projection]
        try:
            base_text = self.table.item(row, base_col_idx).text()
            base_val = float(base_text) if base_text.strip() else 0.0
        except:
            base_val = 0.0
        new_val = max(0, int(round(base_val - val)))
        self._signal_guard = True
        self.table.item(row, self.proj_col_idx).setText(str(new_val))
        self._signal_guard = False

    # ---------------- Invoice ----------------
    def save_invoice(self):
        if not self.current_vendor:
            return

        if self.proj_col_idx == -1 or self.current_projection is None:
            QMessageBox.warning(self, "No Projection", "Please select a projection (1 / 2 / 5 Day) before saving.")
            return

        branch = self.branch_combo.currentText()
        items = []
        for r in range(self.table.rowCount()):
            name_it = self.table.item(r, 0)
            qty_it = self.table.item(r, self.proj_col_idx)
            if not name_it or not qty_it:
                continue
            try:
                qty = int(float(qty_it.text())) if qty_it.text().strip() else 0
            except:
                qty = 0
            if qty > 0:
                items.append([name_it.text(), qty])

        if not items:
            QMessageBox.warning(self, "Warning", "No demand to save from the selected projection.")
            return

        dlg = InvoiceDialog(self.current_vendor, branch, items, self)
        dlg.exec_()

    def cancel_records(self):
        self.table.setRowCount(0)
        self.search_input.clear()
        self.current_vendor = None
        self.proj_col_idx = -1
        self.current_projection = None
        self._update_button_states()

# ----------------------------- Run -----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VendorDemandApp()
    window.show()
    sys.exit(app.exec_())
