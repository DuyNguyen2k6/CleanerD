import sys, os, tempfile, subprocess
from datetime import datetime, timedelta
import platform
import psutil
import socket
from send2trash import send2trash

try:
    import GPUtil
    _HAS_GPU = True
except ImportError:
    _HAS_GPU = False

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QMessageBox, QListWidget, QCheckBox, QProgressBar,
    QFileDialog, QTabWidget, QScrollArea, QGroupBox
)
from PyQt6.QtCore import Qt

# ------ Helper functions, snapshot 1 lần ------
def get_sysinfo_snapshot():
    uname = platform.uname()
    try:
        manufacturer = subprocess.check_output([
            "powershell", "-Command",
            "(Get-CimInstance Win32_ComputerSystem).Manufacturer"
        ], shell=True, text=True, timeout=3).strip()
    except Exception:
        manufacturer = "N/A"
    try:
        model = subprocess.check_output([
            "powershell", "-Command",
            "(Get-CimInstance Win32_ComputerSystem).Model"
        ], shell=True, text=True, timeout=3).strip()
    except Exception:
        model = "N/A"
    try:
        cpu_name = subprocess.check_output([
            "powershell", "-Command",
            "(Get-CimInstance Win32_Processor).Name"
        ], shell=True, text=True, timeout=3).strip()
    except Exception:
        cpu_name = platform.processor() or 'N/A'
    cpu_core = psutil.cpu_count(logical=False)
    cpu_thread = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    ram = psutil.virtual_memory()
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "fstype": part.fstype,
                "used": usage.used,
                "total": usage.total,
                "percent": usage.percent
            })
        except Exception:
            continue
    if _HAS_GPU:
        try:
            gpus = GPUtil.getGPUs()
            gpu_names = [g.name for g in gpus] if gpus else []
        except Exception:
            gpu_names = []
    else:
        try:
            out = subprocess.check_output(
                ["powershell", "-Command", "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name)"],
                shell=True, text=True, timeout=3
            )
            gpu_names = [line.strip() for line in out.strip().splitlines() if line.strip()]
        except Exception:
            gpu_names = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    net_list = []
    for name, iface in stats.items():
        if iface.isup:
            ip = next((a.address for a in addrs[name] if a.family == socket.AF_INET), "N/A")
            net_list.append({
                "name": name,
                "type": "Wifi" if "wi" in name.lower() else "LAN",
                "ip": ip,
                "speed": iface.speed
            })
    net_io = psutil.net_io_counters()
    battery = psutil.sensors_battery()
    return {
        "pcname": uname.node,
        "user": psutil.Process().username(),
        "os": f"{uname.system} {uname.release} ({uname.version})",
        "manufacturer": manufacturer,
        "model": model,
        "boot": get_uptime(),
        "now": get_time(),
        "cpu_name": cpu_name,
        "cpu_core": cpu_core,
        "cpu_thread": cpu_thread,
        "cpu_freq": cpu_freq,
        "ram": ram,
        "disks": disks,
        "gpus": gpu_names,
        "network": net_list,
        "net_sent": net_io.bytes_sent,
        "net_recv": net_io.bytes_recv,
        "battery": battery
    }

def get_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_uptime():
    import time
    uptime_seconds = time.time() - psutil.boot_time()
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    return f"{hours}h {minutes}m"

def format_bytes(num):
    for unit in ['B','KB','MB','GB','TB']:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"

def format_time(seconds):
    if seconds == psutil.POWER_TIME_UNLIMITED:
        return "∞"
    elif seconds == psutil.POWER_TIME_UNKNOWN:
        return "Unknown"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{int(h)}h {int(m)}m"

# --------------- RecycleBinCleaner ---------------
class RecycleBinCleaner(QWidget):
    def __init__(self):
        super().__init__()
        self.log = []
        self._build_ui()
    def _build_ui(self):
        layout = QVBoxLayout()
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
        browsers = QHBoxLayout()
        self.cb_chrome  = QCheckBox("Chrome")
        self.cb_edge    = QCheckBox("Edge")
        self.cb_firefox = QCheckBox("Firefox")
        for cb in [self.cb_chrome, self.cb_edge, self.cb_firefox]:
            browsers.addWidget(cb)
        layout.addLayout(browsers)
        btns = QHBoxLayout()
        btns.addWidget(QPushButton("Xem trước", clicked=self._preview))
        btns.addWidget(QPushButton("Dọn dẹp", clicked=self._clean))
        btns.addWidget(QPushButton("Xuất log…", clicked=self._export_log))
        btns.addWidget(QPushButton("Mở Recycle Bin", clicked=self._open_bin))
        layout.addLayout(btns)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.log_view = QListWidget()
        layout.addWidget(self.log_view, stretch=1)
        self.setLayout(layout)
    def _log(self, msg):
        entry = f"[{datetime.now():%H:%M:%S}] {msg}"
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
        self._log(f"Preview: {len(items)} mục sẽ gửi vào Recycle Bin.")
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
                self._log(f"Sent: {path}")
            except Exception:
                self._log(f"Skip: {path}")
            self.progress.setValue(i)
        bi = total
        if self.cb_chrome.isChecked():
            bi += 1
            for f in ["History","Cookies"]:
                p = os.path.join(os.environ['LOCALAPPDATA'], "Google\\Chrome\\User Data\\Default", f)
                if os.path.exists(p): send2trash(p)
            self._log("Chrome data → Bin")
            self.progress.setValue(bi)
        if self.cb_edge.isChecked():
            bi += 1
            for f in ["History","Cookies"]:
                p = os.path.join(os.environ['LOCALAPPDATA'], "Microsoft\\Edge\\User Data\\Default", f)
                if os.path.exists(p): send2trash(p)
            self._log("Edge data → Bin")
            self.progress.setValue(bi)
        if self.cb_firefox.isChecked():
            bi += 1
            base = os.path.join(os.environ['APPDATA'], "Mozilla\\Firefox\\Profiles")
            if os.path.exists(base):
                for prof in os.listdir(base):
                    for f in ["places.sqlite","cookies.sqlite","downloads.sqlite"]:
                        p = os.path.join(base, prof, f)
                        if os.path.exists(p): send2trash(p)
            self._log("Firefox data → Bin")
            self.progress.setValue(bi)
        QMessageBox.information(self, "Hoàn tất", "Đã gửi vào Recycle Bin! Có thể khôi phục trong Windows Recycle Bin.")
    def _export_log(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Lưu log", filter="Text (*.txt)")
        if fn:
            with open(fn, "w", encoding="utf-8") as f:
                f.write("\n".join(self.log))
            QMessageBox.information(self, "Hoàn tất", f"Đã lưu log tại:\n{fn}")
    def _open_bin(self):
        subprocess.Popen(["explorer", "shell:RecycleBinFolder"], shell=True)

# --------------- SystemInfoTab ---------------
class SystemInfoTab(QWidget):
    def __init__(self):
        super().__init__()
        self.info = get_sysinfo_snapshot()
        self._build_ui()
    def _build_ui(self):
        scroll = QScrollArea()
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        sys_group = QGroupBox("TỔNG QUAN HỆ THỐNG")
        sys_layout = QVBoxLayout()
        sys_layout.addWidget(QLabel(f"PC Name: <b>{self.info['pcname']}</b>"))
        sys_layout.addWidget(QLabel(f"User: <b>{self.info['user']}</b>"))
        sys_layout.addWidget(QLabel(f"OS: <b>{self.info['os']}</b>"))
        sys_layout.addWidget(QLabel(f"System Manufacturer: <b>{self.info['manufacturer']}</b>"))
        sys_layout.addWidget(QLabel(f"System Model: <b>{self.info['model']}</b>"))
        sys_layout.addWidget(QLabel(f"Boot Time: <b>{self.info['boot']}</b>"))
        sys_layout.addWidget(QLabel(f"Time: <b>{self.info['now']}</b>"))
        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group)
        cpu_group = QGroupBox("CPU")
        cpu_layout = QVBoxLayout()
        cpu_layout.addWidget(QLabel(f"Name: <b>{self.info['cpu_name']}</b>"))
        cpu_layout.addWidget(QLabel(f"Cores: <b>{self.info['cpu_core']}</b> | Threads: <b>{self.info['cpu_thread']}</b>"))
        if self.info["cpu_freq"]:
            cpu_layout.addWidget(QLabel(
                f"Base Freq: <b>{self.info['cpu_freq'].max:.0f} MHz</b> | Current: <b>{self.info['cpu_freq'].current:.0f} MHz</b>"))
        cpu_group.setLayout(cpu_layout)
        layout.addWidget(cpu_group)
        ram_group = QGroupBox("RAM")
        ram_layout = QVBoxLayout()
        ram_layout.addWidget(QLabel(f"Total: <b>{self.info['ram'].total // (1024**3)} GB</b>"))
        ram_layout.addWidget(QLabel(f"Available: <b>{self.info['ram'].available // (1024**3)} GB</b>"))
        ram_layout.addWidget(QLabel(f"Usage: <b>{self.info['ram'].percent:.0f}%</b>"))
        ram_group.setLayout(ram_layout)
        layout.addWidget(ram_group)
        disk_group = QGroupBox("Ổ ĐĨA")
        disk_layout = QVBoxLayout()
        for d in self.info["disks"]:
            disk_layout.addWidget(QLabel(
                f"{d['device']} ({d['fstype']}): {d['used'] // (1024**3)}GB / {d['total'] // (1024**3)}GB ({d['percent']:.0f}%)"
            ))
        disk_group.setLayout(disk_layout)
        layout.addWidget(disk_group)
        gpu_group = QGroupBox("GPU")
        gpu_layout = QVBoxLayout()
        if self.info["gpus"]:
            for n in self.info["gpus"]:
                gpu_layout.addWidget(QLabel(f"Name: <b>{n}</b>"))
        else:
            gpu_layout.addWidget(QLabel("Không phát hiện GPU hoặc thiếu driver."))
        gpu_group.setLayout(gpu_layout)
        layout.addWidget(gpu_group)
        net_group = QGroupBox("NETWORK")
        net_layout = QVBoxLayout()
        for n in self.info["network"]:
            net_layout.addWidget(QLabel(f"<b>{n['name']}</b>: {n['type']}"))
            net_layout.addWidget(QLabel(f"  IP: {n['ip']} | Speed: {n['speed']} Mbps"))
        net_layout.addWidget(QLabel(f"Tổng đã gửi: <b>{format_bytes(self.info['net_sent'])}</b> | Nhận: <b>{format_bytes(self.info['net_recv'])}</b>"))
        net_group.setLayout(net_layout)
        layout.addWidget(net_group)
        battery = self.info["battery"]
        if battery:
            bat_group = QGroupBox("PIN")
            bat_layout = QVBoxLayout()
            bat_layout.addWidget(QLabel(f"Charge: <b>{battery.percent:.0f}%</b>"))
            bat_layout.addWidget(QLabel(f"Plugged in: <b>{'Yes' if battery.power_plugged else 'No'}</b>"))
            bat_layout.addWidget(QLabel(f"Time left: <b>{format_time(battery.secsleft)}</b>"))
            bat_group.setLayout(bat_layout)
            layout.addWidget(bat_group)
        container.setLayout(layout)
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

# --------------- MAIN APP ---------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    tabs = QTabWidget()
    tabs.addTab(RecycleBinCleaner(), "Cleaner")
    tabs.addTab(SystemInfoTab(), "System Info")
    tabs.setWindowTitle("System Cleaner & Info")
    tabs.setFixedSize(850, 750)
    tabs.show()
    sys.exit(app.exec())
