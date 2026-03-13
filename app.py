import sys
import threading
import socket
import requests
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtWidgets import *

found_streams = {}
running = False


def get_country(ip):
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        return r.json().get("country_name", "Unknown")
    except:
        return "Unknown"


def stream_online(ip, port):
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect((ip, port))
        s.close()
        return True
    except:
        return False


def detect_name(ip, port):

    try:
        r = requests.get(f"http://{ip}:{port}", timeout=3)

        if "#EXTINF" in r.text:
            for line in r.text.splitlines():
                if "#EXTINF" in line:
                    return line.split(",")[-1]

    except:
        pass

    return "Unknown Channel"


def scan_ips():

    global running

    while running:

        for a in range(1,255):
            for b in range(1,255):

                ip = f"192.{a}.{b}.1"

                port = 80

                addr = f"{ip}:{port}"

                if addr in found_streams:
                    continue

                if stream_online(ip,port):

                    name = detect_name(ip,port)
                    country = get_country(ip)

                    found_streams[addr] = {
                        "name": name,
                        "country": country
                    }


def export_m3u():

    path,_ = QFileDialog.getSaveFileName(None,"Save","streams.m3u")

    if not path:
        return

    with open(path,"w",encoding="utf8") as f:

        f.write("#EXTM3U\n")

        for addr,meta in found_streams.items():

            f.write(
                f'#EXTINF:-1 group-title="{meta["country"]}",{meta["name"]}\n'
            )

            f.write(f"http://{addr}\n")


class Window(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Stream Finder PRO")

        self.resize(700,500)

        layout = QVBoxLayout()

        buttons = QHBoxLayout()

        self.start = QPushButton("Start Scan")
        self.stop = QPushButton("Stop")
        self.export = QPushButton("Export M3U")

        buttons.addWidget(self.start)
        buttons.addWidget(self.stop)
        buttons.addWidget(self.export)

        self.list = QListWidget()
        self.label = QLabel("Streams: 0")

        layout.addLayout(buttons)
        layout.addWidget(self.list)
        layout.addWidget(self.label)

        self.setLayout(layout)

        self.start.clicked.connect(self.start_scan)
        self.stop.clicked.connect(self.stop_scan)
        self.export.clicked.connect(export_m3u)

        threading.Thread(target=self.update_ui,daemon=True).start()


    def start_scan(self):

        global running

        running = True

        threading.Thread(target=scan_ips,daemon=True).start()


    def stop_scan(self):

        global running

        running = False


    def update_ui(self):

        import time

        while True:

            self.list.clear()

            for addr in found_streams.keys():
                self.list.addItem(addr)

            self.label.setText(
                f"Streams Found: {len(found_streams)}"
            )

            time.sleep(2)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    w = Window()
    w.show()

    sys.exit(app.exec())
