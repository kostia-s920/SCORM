from http.server import BaseHTTPRequestHandler
import base64
import os
import json
import tempfile
import sys

# Додаємо батьківську директорію до шляху імпорту
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from scripts.html_converter import convert_html_to_scorm
except ImportError:
    def convert_html_to_scorm(html_path, output_path, title=None, scorm_version='2004', include_resources=True):
        # Базова заглушка для тестування
        print(f"Simulating HTML conversion: {html_path} -> {output_path}")
        with open(output_path, 'wb') as f:
            f.write(b'Test SCORM Package')
        return True


# Спеціальний клас-обробник для Vercel
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode('utf-8'))
        except:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
            return

        file_type = body.get('file_type', '').lower()
        file_content_base64 = body.get('file_content', '')
        file_name = body.get('file_name', 'document')
        title = body.get('title', '')
        scorm_version = body.get('scorm_version', '2004')

        # Відключаємо PDF-конвертацію тимчасово
        if file_type == 'pdf':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "PDF conversion is temporarily disabled for testing"}).encode())
            return

        # Перевірка підтримки типу файлу
        if file_type not in ['html', 'htm']:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(
                {"error": f"Unsupported file type: {file_type}. Only HTML is supported in this test."}).encode())
            return

        try:
            file_content = base64.b64decode(file_content_base64)
        except:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid Base64 file"}).encode())
            return

        input_path = None
        output_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as temp_file:
                temp_file.write(file_content)
                input_path = temp_file.name

            output_path = os.path.join(tempfile.gettempdir(), f"{file_name}_scorm.zip")

            # Конвертуємо тільки HTML
            result = convert_html_to_scorm(input_path, output_path, title=title, scorm_version=scorm_version)

            if not result or not os.path.exists(output_path):
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "SCORM generation failed"}).encode())
                return

            with open(output_path, 'rb') as f:
                scorm_content = f.read()

            scorm_base64 = base64.b64encode(scorm_content).decode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "scorm_package": scorm_base64,
                "file_name": f"{file_name}_scorm.zip"
            }).encode())

        finally:
            if input_path and os.path.exists(input_path):
                os.unlink(input_path)
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


# Надаємо Vercel доступ до обробника через спрощений інтерфейс
def handler(req):
    return Handler().do_POST()