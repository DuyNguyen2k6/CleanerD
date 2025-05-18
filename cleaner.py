import sys, os, tempfile, subprocess
from datetime import datetime, timedelta
from send2trash import send2trash
import platform
import psutil
import os, json
from datetime import datetime, timedelta

CACHE_PATH = os.path.join(os.getenv("APPDATA"), "MyCleaner", "cache.json")

def load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def is_fresh(entry, max_age_seconds):
    """Kiểm tra timestamp còn tươi không."""
    ts = datetime.fromisoformat(entry.get("timestamp"))
    return datetime.now() - ts < timedelta(seconds=max_age_seconds)

# --- Ví dụ cho CPU name ---

def get_cpu_name_cached(max_age_seconds=3600):
    cache = load_cache()
    if "cpu_name" in cache and is_fresh(cache["cpu_name"], max_age_seconds):
        return cache["cpu_name"]["value"]
    # --- Nếu cache không hợp lệ, tính toán mới ---
    name = get_cpu_name()   # hàm gốc của bạn
    cache["cpu_name"] = {
        "value": name,
        "timestamp": datetime.now().isoformat()
    }
    save_cache(cache)
    return name

# --- Ví dụ cho danh sách temp files ---

def gather_items_cached(max_age_seconds=300):
    cache = load_cache()
    if "temp_items" in cache and is_fresh(cache["temp_items"], max_age_seconds):
        return cache["temp_items"]["value"]
    items = gather_items()   # hàm quét tempfile.gettempdir()
    cache["temp_items"] = {
        "value": items,
        "timestamp": datetime.now().isoformat()
    }
    save_cache(cache)
    return items


# GPU detection
try:
    import GPUtil
    _HAS_GPU = True
except ImportError:
    _HAS_GPU = False
# WMI for detailed info on Windows
try:
    import wmi
    _HAS_WMI = True
except ImportError:
    _HAS_WMI = False

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QMessageBox, QListWidget, QCheckBox, QProgressBar,
    QFileDialog, QTabWidget, QScrollArea
)
from PyQt6.QtCore import Qt


def get_cpu_name():
    # 1) Thử WMI nếu đã cài module wmi
    if _HAS_WMI:
        try:
            c = wmi.WMI()
            return c.Win32_Processor()[0].Name.strip()
        except Exception:
            pass

    # 2) Thử gọi PowerShell CIM trước (thay cho wmic)
    try:
        out = subprocess.check_output(
            ["powershell", "-Command", "(Get-CimInstance Win32_Processor).Name"],
            shell=True, text=True
        ).strip()
        if out:
            return out
    except Exception:
        pass

    # 3) Fallback về lệnh wmic cũ (nếu vẫn còn)
    try:
        lines = subprocess.check_output(
            "wmic cpu get Name", shell=True, text=True
        ).strip().splitlines()
        if len(lines) >= 2:
            return lines[1].strip()
    except Exception:
        pass

    # 4) Cuối cùng dùng platform nếu tất cả thất bại
    uname = platform.uname()
    return platform.processor() or uname.processor or 'N/A'



def get_gpu_names():
    names = []
    if _HAS_GPU:
        try:
            gpus = GPUtil.getGPUs()
            names = [g.name for g in gpus]
        except Exception:
            names = []
    if not names and _HAS_WMI:
        try:
            w = wmi.WMI()
            names = [gpu.Name for gpu in w.Win32_VideoController()]
        except Exception:
            names = []
    if not names:
        try:
            out = subprocess.check_output(
                "wmic path win32_VideoController get Name", shell=True, text=True
            ).strip().splitlines()
            names = [line.strip() for line in out[1:] if line.strip()]
        except Exception:
            names = []
    return names


class RecycleBinCleaner(QWidget):
    def __init__(self):
        super().__init__()
        self.log = []
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("System Cleaner")
        layout = QVBoxLayout()

        # Filters
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Size > (MB):"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(0, 1024)
        filt.addWidget(self.size_spin)
        filt.addSpacing(20)
        filt.addWidget(QLabel("Age > (days):"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(0, 365)
        filt.addWidget(self.days_spin)
        layout.addLayout(filt)

        # Browser options
        browsers = QHBoxLayout()
        self.cb_chrome  = QCheckBox("Chrome: History/Cookies")
        self.cb_edge    = QCheckBox("Edge: History/Cookies")
        self.cb_firefox = QCheckBox("Firefox: History/Cookies")
        browsers.addWidget(self.cb_chrome)
        browsers.addWidget(self.cb_edge)
        browsers.addWidget(self.cb_firefox)
        layout.addLayout(browsers)

        # Buttons
        btns = QHBoxLayout()
        btns.addWidget(QPushButton("Xem trước", clicked=self._preview))
        btns.addWidget(QPushButton("Dọn dẹp", clicked=self._clean))
        btns.addWidget(QPushButton("Xuất log…", clicked=self._export_log))
        btns.addWidget(QPushButton("Mở Recycle Bin", clicked=self._open_bin))
        layout.addLayout(btns)

        # Progress & Log
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.log_view = QListWidget()
        layout.addWidget(self.log_view, stretch=1)

        self.setLayout(layout)

    def _log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        entry = f"[{t}] {msg}"
        self.log.append(entry)
        self.log_view.addItem(entry)
        QApplication.processEvents()

    def _gather_items(self):
        root = tempfile.gettempdir()
        size_thresh = self.size_spin.value() * 1024**2
        age_thresh  = datetime.now() - timedelta(days=self.days_spin.value())
        items = []
        for name in os.listdir(root):
            path = os.path.join(root, name)
            try:
                if os.path.isfile(path) and os.path.getsize(path) < size_thresh:
                    continue
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                if mtime > age_thresh:
                    continue
            except Exception:
                pass
            items.append(path)
        return items

    def _preview(self):
        self.log_view.clear()
        items = self._gather_items()
        self._log(f"Preview: {len(items)} mục sẽ được gửi vào Recycle Bin.")
        for p in items:
            self.log_view.addItem("  • " + p)

    def _clean(self):
        items = self._gather_items()
        total = len(items)
        br_tasks = sum([self.cb_chrome.isChecked(), self.cb_edge.isChecked(), self.cb_firefox.isChecked()])
        if total + br_tasks == 0:
            QMessageBox.information(self, "Empty", "Không có gì để dọn.")
            return
        if QMessageBox.question(
            self, "Xác nhận",
            f"Bạn sẽ gửi {total} mục và {br_tasks} mục browser vào Recycle Bin. Tiếp tục?"
        ) != QMessageBox.StandardButton.Yes:
            return
        self.progress.setValue(0)
        self.progress.setMaximum(total + br_tasks)
        for i, path in enumerate(items, 1):
            try:
                send2trash(path)
                self._log(f"Sent to Bin: {path}")
            except Exception:
                self._log(f"Skip: {path}")
            self.progress.setValue(i)
        bi = total
        # Browser cleanup
        if self.cb_chrome.isChecked():
            bi += 1
            for f in ["History","Cookies"]:
                p = os.path.join(os.environ['LOCALAPPDATA'], f"Google\\Chrome\\User Data\\Default\\{f}")
                if os.path.exists(p): send2trash(p)
            self._log("Chrome data → Bin")
            self.progress.setValue(bi)
        if self.cb_edge.isChecked():
            bi += 1
            for f in ["History","Cookies"]:
                p = os.path.join(os.environ['LOCALAPPDATA'], f"Microsoft\\Edge\\User Data\\Default\\{f}")
                if os.path.exists(p): send2trash(p)
            self._log("Edge data → Bin")
            self.progress.setValue(bi)
        if self.cb_firefox.isChecked():
            bi += 1
            prof_base = os.path.join(os.environ['APPDATA'], "Mozilla\\Firefox\\Profiles")
            for prof in os.listdir(prof_base):
                for f in ["places.sqlite","cookies.sqlite","downloads.sqlite"]:
                    p = os.path.join(prof_base, prof, f)
                    if os.path.exists(p): send2trash(p)
            self._log("Firefox data → Bin")
            self.progress.setValue(bi)
        QMessageBox.information(self, "Hoàn tất", "Đã gửi tất cả vào Recycle Bin! Bạn có thể dùng Windows Recycle Bin để khôi phục.")

    def _export_log(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Lưu log", filter="Text (*.txt)")
        if fn:
            with open(fn, "w", encoding="utf-8") as f:
                f.write("\n".join(self.log))
            QMessageBox.information(self, "Hoàn tất", f"Đã lưu log tại:\n{fn}")

    def _open_bin(self):
        subprocess.Popen(["explorer", "shell:RecycleBinFolder"], shell=True)


class SystemInfoTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea()
        container = QWidget()
        layout = QVBoxLayout()

        uname = platform.uname()
        layout.addWidget(QLabel(f"Hệ điều hành: {uname.system} {uname.release} ({uname.version})"))
        layout.addWidget(QLabel(f"Kiến trúc: {uname.machine}"))

        cpu_name = get_cpu_name()
        layout.addWidget(QLabel(f"Bộ xử lý (CPU): {cpu_name}"))

        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024**3)
        layout.addWidget(QLabel(f"Bộ nhớ RAM: {total_gb:.1f} GB"))

        gpu_names = get_gpu_names()
        if gpu_names:
            layout.addWidget(QLabel(f"Đồ họa (GPU): {', '.join(gpu_names)}"))
        else:
            layout.addWidget(QLabel("Đồ họa (GPU): Không phát hiện hoặc thiếu thư viện"))

        partitions = psutil.disk_partitions(all=False)
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                percent = usage.percent
                used_gb = usage.used / (1024**3)
                total_d = usage.total / (1024**3)
                h = QHBoxLayout()
                # Hiển thị ký tự ổ đĩa
                drive_label = QLabel(part.device.rstrip('\\'))  # ví dụ 'D:' 
                h.addWidget(drive_label)
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(int(percent))
                bar.setFormat(f"{used_gb:.1f}/{total_d:.1f} GB ({percent:.0f}%)")
                bar.setTextVisible(True)
                bar.setStyleSheet(
                    "QProgressBar { border: 1px solid #AAA; text-align: center; }"
                    "QProgressBar::chunk { background-color: #409EFF; }"
                )
                h.addWidget(bar)
                layout.addLayout(h)
            except PermissionError:
                continue

        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)

        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    tabs = QTabWidget()
    tabs.addTab(RecycleBinCleaner(), "Cleaner")
    tabs.addTab(SystemInfoTab(), "System Info")
    tabs.setWindowTitle("System Cleaner & Info")
    tabs.setFixedSize(800, 600)
    tabs.show()
    sys.exit(app.exec())
