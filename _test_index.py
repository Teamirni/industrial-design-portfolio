import subprocess, threading, time, urllib.request, os, http.server, socketserver, pymupdf

BASE = r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8141
URL = f"http://127.0.0.1:{PORT}/index.html"
PDF = os.path.join(BASE, "_test_index.pdf")
PNG = os.path.join(BASE, "_test_index_p0.png")

def start_server():
    os.chdir(BASE)
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

httpd = start_server()
for _ in range(50):
    try:
        urllib.request.urlopen(URL, timeout=1); break
    except Exception:
        time.sleep(0.2)

if os.path.exists(PDF): os.remove(PDF)
cmd = [EDGE, "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
       "--no-pdf-header-footer", f"--print-to-pdf={PDF}",
       "--virtual-time-budget=15000", URL]
r = subprocess.run(cmd, capture_output=True, timeout=120)
print("PDF rc", r.returncode, "exists", os.path.exists(PDF), "size", os.path.getsize(PDF) if os.path.exists(PDF) else 0)

doc = pymupdf.open(PDF)
print("PAGES", doc.page_count)
page = doc.load_page(0)
pix = page.get_pixmap(dpi=110)
pix.save(PNG)
print("PNG saved", os.path.getsize(PNG))
httpd.shutdown()
