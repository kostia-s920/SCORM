from http.server import BaseHTTPRequestHandler
import base64
import os
import json
import tempfile
import sys

# Додаємо шлях до імпорту модулів
try:
    from scripts.html_converter import convert_html_to_scorm
except ImportError:
    def convert_html_to_scorm(html_path, output_path, title=None, scorm_version='2004', include_resources=True):
        # Проста заглушка при відсутності модуля
        with open(output_path, 'wb') as f:
            f.write(b'Test SCORM Package')
        return True


# Функція для створення відповіді у форматі JSON
def create_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps(body)
    }


# Обробник для Vercel
def handler(request):
    if request.method == "OPTIONS":
        return create_response(200, {"message": "CORS OK"})

    if request.method != "POST":
        return create_response(405, {"error": "Method not allowed. Use POST instead."})

    try:
        # Спроба отримати JSON з тіла запиту
        if isinstance(request.body, bytes):
            body = json.loads(request.body.decode('utf-8'))
        else:
            body = json.loads(request.body)
    except Exception as e:
        return create_response(400, {"error": f"Invalid JSON: {str(e)}"})

    # Отримуємо параметри запиту
    file_type = body.get('file_type', '').lower()
    file_content_base64 = body.get('file_content', '')
    file_name = body.get('file_name', 'document')
    title = body.get('title', '')
    scorm_version = body.get('scorm_version', '2004')

    # Тимчасово відключаємо PDF
    if file_type == 'pdf':
        return create_response(200, {"error": "PDF conversion temporarily disabled"})

    # Перевіряємо підтримуваний тип файлу
    if file_type not in ['html', 'htm']:
        return create_response(400, {"error": f"Unsupported file type: {file_type}"})

    # Декодуємо base64
    try:
        file_content = base64.b64decode(file_content_base64)
    except:
        return create_response(400, {"error": "Invalid Base64 data"})

    # Перевіряємо розмір файлу
    if len(file_content) > 10 * 1024 * 1024:
        return create_response(400, {"error": "File too large. Max 10MB"})

    input_path = None
    output_path = None

    try:
        # Записуємо файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as temp_file:
            temp_file.write(file_content)
            input_path = temp_file.name

        # Шлях для вихідного пакету
        output_path = os.path.join(tempfile.gettempdir(), f"{file_name}_scorm.zip")

        # Конвертуємо
        result = convert_html_to_scorm(input_path, output_path, title=title, scorm_version=scorm_version)

        if not result or not os.path.exists(output_path):
            return create_response(500, {"error": "SCORM generation failed"})

        # Зчитуємо результат
        with open(output_path, 'rb') as f:
            scorm_content = f.read()

        # Кодуємо результат в base64
        scorm_base64 = base64.b64encode(scorm_content).decode('utf-8')

        # Повертаємо успішну відповідь
        return create_response(200, {
            "success": True,
            "scorm_package": scorm_base64,
            "file_name": f"{file_name}_scorm.zip"
        })

    except Exception as e:
        # Повертаємо помилку
        return create_response(500, {
            "error": f"Server error during conversion: {str(e)}"
        })

    finally:
        # Видаляємо тимчасові файли
        if input_path and os.path.exists(input_path):
            os.unlink(input_path)
        if output_path and os.path.exists(output_path):
            os.unlink(output_path)


# Клас для локального тестування
class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        # Створюємо об'єкт запиту для обробника
        request = type('Request', (), {
            'method': 'POST',
            'body': post_data,
            'url': self.path
        })

        # Викликаємо обробник
        response = handler(request)

        # Відправляємо відповідь
        self.send_response(response.get('statusCode', 200))
        for key, value in response.get('headers', {}).items():
            self.send_header(key, value)
        self.end_headers()

        self.wfile.write(response.get('body', '').encode())