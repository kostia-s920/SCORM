from http.server import BaseHTTPRequestHandler
import base64
import os
import json
import tempfile

from scripts.html_converter import convert_html_to_scorm
from scripts.pdf_converter import convert_pdf_to_scorm


# Функція-обробник для Vercel
def handler(request):
    # Якщо це OPTIONS-запит (для CORS)
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "POST, OPTIONS"
            },
            "body": ""
        }

    # Обробка POST-запитів
    if request.method == "POST":
        try:
            # Отримуємо тіло запиту
            body = json.loads(request.body)
        except:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Invalid JSON"})
            }

        file_type = body.get('file_type', '').lower()
        file_content_base64 = body.get('file_content', '')
        file_name = body.get('file_name', 'document')
        title = body.get('title', '')
        scorm_version = body.get('scorm_version', '2004')

        try:
            file_content = base64.b64decode(file_content_base64)
        except:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Invalid Base64 file"})
            }

        if len(file_content) > 10 * 1024 * 1024:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "File too large. Max 10MB"})
            }

        input_path = None
        output_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as temp_file:
                temp_file.write(file_content)
                input_path = temp_file.name

            output_path = os.path.join(tempfile.gettempdir(), f"{file_name}_scorm.zip")

            result = False
            if file_type in ['html', 'htm']:
                result = convert_html_to_scorm(input_path, output_path, title=title, scorm_version=scorm_version)
            elif file_type == 'pdf':
                result = convert_pdf_to_scorm(input_path, output_path, title=title, scorm_version=scorm_version)
            else:
                return {
                    "statusCode": 400,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": f"Unsupported file type: {file_type}"})
                }

            if not result or not os.path.exists(output_path):
                return {
                    "statusCode": 500,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": "SCORM generation failed"})
                }

            with open(output_path, 'rb') as f:
                scorm_content = f.read()

            scorm_base64 = base64.b64encode(scorm_content).decode('utf-8')

            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "success": True,
                    "scorm_package": scorm_base64,
                    "file_name": f"{file_name}_scorm.zip"
                })
            }

        finally:
            if input_path and os.path.exists(input_path):
                os.unlink(input_path)
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)
    else:
        return {
            "statusCode": 405,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Method not allowed"})
        }


# Клас для обробки HTTP-запитів (для локального тестування і для сумісності з Vercel)
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        # Створюємо об'єкт запиту, який буде сумісний з очікуваннями нашого обробника
        request = type('Request', (), {
            'method': 'POST',
            'body': post_data,
            'url': self.path
        })

        response = handler(request)

        self.send_response(response.get('statusCode', 200))
        for key, value in response.get('headers', {}).items():
            self.send_header(key, value)
        self.end_headers()

        self.wfile.write(response.get('body', '').encode())

    def do_OPTIONS(self):
        request = type('Request', (), {'method': 'OPTIONS', 'body': ''})
        response = handler(request)

        self.send_response(response.get('statusCode', 200))
        for key, value in response.get('headers', {}).items():
            self.send_header(key, value)
        self.end_headers()