"""Simple HTTP server for ICS calendar subscription."""

from http.server import HTTPServer, BaseHTTPRequestHandler
from notes.manager import NoteManager
from notes.ics import generate_ics


class CalendarHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/calendar.ics", "/notes/calendar.ics", "/"):
            mgr = NoteManager()
            notes = mgr.list_notes(include_done=False, limit=9999)
            cal_notes = [n for n in notes if n.due_date or n.category.value in ("todo", "work")]
            ics_content = generate_ics(cal_notes)

            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=notes.ics")
            self.end_headers()
            self.wfile.write(ics_content.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found. Use /calendar.ics")

    def log_message(self, format, *args):
        print(f"[Calendar Server] {args[0]}")


def run_server(host: str = "0.0.0.0", port: int = 8080):
    server = HTTPServer((host, port), CalendarHandler)
    print(f"📅 日历订阅服务已启动: http://{host}:{port}/calendar.ics")
    print(f"   Apple Calendar / Google Calendar 可直接订阅此 URL")
    print(f"   按 Ctrl+C 停止服务")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()
