# STREAM FINDER ULTRA
# Multi‑engine discovery + protocol detection
# Sources: Censys + Shodan + ZoomEye + Netlas
# Detects: HTTP IPTV, HLS (.m3u8), RTSP, UDP MPEG‑TS
# Output: IP:PORT list + organized M3U playlist by country

import sys
import threading
import queue
import requests
import socket
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QLabel, QFileDialog
)

# ================= API KEYS =================

CENSYS_API_ID = ""
CENSYS_API_SECRET = ""

SHODAN_API_KEY = ""
ZOOMEYE_API_KEY = ""
NETLAS_API_KEY = ""

SEARCH_TERMS = [
    "video/mp2t",
    "m3u8",
    "rtsp",
]

# ================= GLOBAL =================

running = False
result_queue = queue.Queue()
found_streams = {}

# ================= GEO =================

def get_country(ip):

    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
        return r.json().get("country_name", "Unknown")
    except:
        return "Unknown"

# ================= DETECTORS =================

def detect_http_stream(ip, port):

    try:
        url = f"http://{ip}:{port}"

        r = requests.get(url, timeout=3)

        text = r.text.lower()

        if "#extm3u" in text or ".m3u8" in text:
            return "HLS Stream"

        if "#extinf" in text:
            return "IPTV Playlist"

    except:
        pass

    return None


def detect_rtsp(ip, port):

    try:
        s = socket.socket()
        s.settimeout(2)

        s.connect((ip, port))

        request = "OPTIONS rtsp://{}:{}/ RTSP/1.0\r\nCSeq: 1\r\n\r\n".format(ip,port)

        s.send(request.encode())

        data = s.recv(1024).decode(errors="ignore")

        if "RTSP" in data:
            return "RTSP Stream"

    except:
        pass

    return None


def detect_udp(ip, port):

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)

        s.sendto(b"test", (ip, port))

        data,_ = s.recvfrom(188*2)

        if len(data) >= 188:
            return "UDP MPEGTS"

    except:
        pass

    return None

# ================= ENGINE RESULTS =================

def add_result(ip, port):

    addr = f"{ip}:{port}"

    if addr in found_streams:
        return

    name = None

    name = detect_http_stream(ip,port)

    if not name:
        name = detect_rtsp(ip,port)

    if not name:
        name = detect_udp(ip,port)

    if not name:
        return

    country = get_country(ip)

    found_streams[addr] = {
        "name": name,
        "country": country
    }

    result_queue.put(addr)

# ================= SEARCH ENGINES =================

def search_censys():

    if not CENSYS_API_ID:
        return

    url = "https://search.censys.io/api/v2/hosts/search"

    cursor = None

    while running:

        payload = {
            "q": 'services.banner: "video/mp2t"',
            "per_page": 100
        }

        if cursor:
            payload["cursor"] = cursor

        r = requests.post(url, auth=(CENSYS_API_ID,CENSYS_API_SECRET), json=payload)

        if r.status_code != 200:
            break

        data = r.json()

        for host in data.get("result",{}).get("hits",[]):

            ip = host.get("ip")

            for svc in host.get("services",[]):

                port = svc.get("port")

                if ip and port:
                    add_result(ip,port)

        cursor = data.get("result",{}).get("links",{}).get("next")

        if not cursor:
            break


def search_shodan():

    if not SHODAN_API_KEY:
        return

    page = 1

    while running:

        url = f"https://api.shodan.io/shodan/host/search?key={SHODAN_API_KEY}&query=video/mp2t&page={page}"

        r = requests.get(url)

        if r.status_code != 200:
            break

        data = r.json()

        for m in data.get("matches",[]):

            ip = m.get("ip_str")
            port = m.get("port")

            if ip and port:
                add_result(ip,port)

        page += 1


def search_zoomeye():

    if not ZOOMEYE_API_KEY:
        return

    headers = {"API-KEY":ZOOMEYE_API_KEY}

    page = 1

    while running:

        url = f"https://api.zoomeye.org/host/search?query=video/mp2t&page={page}"

        r = requests.get(url,headers=headers)

        if r.status_code != 200:
            break

        data = r.json()

        for m in data.get("matches",[]):

            ip = m.get("ip")

            port = None

            portinfo = m.get("portinfo")

            if isinstance(portinfo,dict):
                port = portinfo.get("port")

            if ip and port:
                add_result(ip,port)

        page += 1


def search_netlas():

    if not NETLAS_API_KEY:
        return

    headers = {"X-Api-Key":NETLAS_API_KEY}

    page = 0

    while running:

        url = f"https://app.netlas.io/api/hosts/?q=video/mp2t&page={page}"

        r = requests.get(url,headers=headers)

        if r.status_code != 200:
            break

        data = r.json()

        for item in data.get("items",[]):

            ip = item.get("ip")

            for port in item.get("ports",[]):

                if ip and port:
                    add_result(ip,port)

        page += 1

# ================= M3U EXPORT =================

def export_m3u():

    path,_ = QFileDialog.getSaveFileName(None,"Save Playlist","streams.m3u")

    if not path:
        return

    by_country = {}

    for addr,meta in found_streams.items():

        by_country.setdefault(meta["country"],[]).append((addr,meta))

    with open(path,"w",encoding="utf8") as f:

        f.write("#EXTM3U\n")

        for country,items in by_country.items():

            for addr,meta in items:

                f.write(f'#EXTINF:-1 group-title="{country}",{meta["name"]}\n')

                f.write(f"http://{addr}\n")

# ================= GUI =================

class Window(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Stream Finder ULTRA")

        self.resize(900,600)

        layout = QVBoxLayout()

        buttons = QHBoxLayout()

        self.start_btn = QPushButton("Start Global Scan")
        self.stop_btn = QPushButton("Stop")
        self.export_btn = QPushButton("Export M3U")

        buttons.addWidget(self.start_btn)
        buttons.addWidget(self.stop_btn)
        buttons.addWidget(self.export_btn)

        self.listbox = QListWidget()

        self.label = QLabel("Streams Found: 0")

        layout.addLayout(buttons)
        layout.addWidget(self.listbox)
        layout.addWidget(self.label)

        self.setLayout(layout)

        self.start_btn.clicked.connect(self.start_scan)
        self.stop_btn.clicked.connect(self.stop_scan)
        self.export_btn.clicked.connect(export_m3u)

        threading.Thread(target=self.ui_loop,daemon=True).start()

    def start_scan(self):

        global running

        running = True

        threading.Thread(target=search_censys,daemon=True).start()
        threading.Thread(target=search_shodan,daemon=True).start()
        threading.Thread(target=search_zoomeye,daemon=True).start()
        threading.Thread(target=search_netlas,daemon=True).start()

    def stop_scan(self):

        global running

        running = False

    def ui_loop(self):

        import time

        while True:

            while not result_queue.empty():

                addr = result_queue.get()

                self.listbox.addItem(addr)

            self.label.setText(f"Streams Found: {len(found_streams)}")

            time.sleep(1)

# ================= MAIN =================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    w = Window()

    w.show()

    sys.exit(app.exec())
