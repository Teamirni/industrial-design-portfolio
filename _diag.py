import subprocess, threading, time, urllib.request, os, http.server, socketserver

BASE = r"E:\WorkBuddy工作路径\工业设计作品集\portfolio-v2"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 8140
URL = f"http://127.0.0.1:{PORT}/index.html"
SUMMARY = os.path.join(BASE, "_diag_summary.txt")

def log(msg):
    with open(SUMMARY, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

os.chdir(BASE)
open(SUMMARY, "w", encoding="utf-8").close()

def start_server():
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    out = (r.stdout or b"").decode("utf-8", "replace")
    err = (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out, err

httpd = start_server()
for _ in range(50):
    try:
        urllib.request.urlopen(URL, timeout=1); break
    except Exception:
        time.sleep(0.2)

rc, out, err = run([EDGE, "--version"])
log(f"EDGE VERSION: {out.strip()} | rc={rc}")

# Screenshot tests
for mode in ["old", "new"]:
    hl = "--headless" if mode == "old" else "--headless=new"
    outp = os.path.join(BASE, f"_shot_{mode}.png")
    if os.path.exists(outp): os.remove(outp)
    cmd = [EDGE, hl, "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
           "--hide-scrollbars", "--window-size=1280,1700",
           f"--screenshot={outp}", "--virtual-time-budget=12000", URL]
    rc, out, err = run(cmd)
    sz = os.path.getsize(outp) if os.path.exists(outp) else 0
    log(f"SCREENSHOT {mode}: rc={rc} exists={os.path.exists(outp)} size={sz}")
    log(f"  err: {err[:300]}")

# Print-to-PDF tests
for mode in ["old", "new"]:
    hl = "--headless" if mode == "old" else "--headless=new"
    outp = os.path.join(BASE, f"_pdf_{mode}.pdf")
    if os.path.exists(outp): os.remove(outp)
    cmd = [EDGE, hl, "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
           "--no-pdf-header-footer", f"--print-to-pdf={outp}",
           "--virtual-time-budget=12000", URL]
    rc, out, err = run(cmd)
    sz = os.path.getsize(outp) if os.path.exists(outp) else 0
    log(f"PRINT_PDF {mode}: rc={rc} exists={os.path.exists(outp)} size={sz}")
    log(f"  err: {err[:300]}")

httpd.shutdown()
log("DONE")
