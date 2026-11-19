"""Exercise real SMTP protocol on loopback; no external mail is transmitted."""

import socketserver
import threading
from app.core.config import Settings
from app.integrations.notifications import send_email_direct


def test_real_local_smtp_submission_and_multipart_template():
    received = []

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b"220 local-test\r\n")
            while True:
                line = self.rfile.readline()
                if not line:
                    break
                command = line.split(b" ", 1)[0].strip().upper()
                if command == b"DATA":
                    self.wfile.write(b"354 Continue\r\n")
                    parts = []
                    while True:
                        line = self.rfile.readline()
                        if line == b".\r\n" or not line:
                            break
                        parts.append(line)
                    received.append(b"".join(parts))
                    self.wfile.write(b"250 Accepted\r\n")
                elif command == b"QUIT":
                    self.wfile.write(b"221 Bye\r\n")
                    break
                else:
                    self.wfile.write(b"250 OK\r\n")

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            settings = Settings(
                _env_file=None,
                smtp_host="127.0.0.1",
                smtp_port=server.server_address[1],
                smtp_from="sender@example.com",
                smtp_use_tls=False,
            )
            result = send_email_direct(
                to_address="recipient@example.com",
                subject="Private setup",
                body="Private setup text",
                html_body="<p>Private setup text</p>",
                settings=settings,
            )
            assert result["status"] == "sent"
            assert len(received) == 1
            assert b"multipart/alternative" in received[0]
            assert b"text/html" in received[0] and b"text/plain" in received[0]
        finally:
            server.shutdown()
            thread.join()
