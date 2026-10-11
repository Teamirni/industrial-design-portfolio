import subprocess, threading, time, urllib.request, os, http.server, socketserver

BASE = r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8137
URL = f"http://127.0.0.1:{PORT}/index.html"

def start_server():
    os.chdir(BASE)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

httpd = start_server()
for _ in range(50):
    try:
        urllib.request.urlopen(URL, timeout=1); break
    except Exception:
        time.sleep(0.2)

out = os.path.join(BASE, "_shot_index.png")
cmd = [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
       "--window-size=1280,1700", f"--screenshot={out}",
       "--virtual-time-budget=15000", URL]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
print("returncode", r.returncode)
print("STDERR_TAIL", r.stderr[-1500:])
print("OUT_EXISTS", os.path.exists(out), os.path.getsize(out) if os.path.exists(out) else 0)
httpd.shutdown()
