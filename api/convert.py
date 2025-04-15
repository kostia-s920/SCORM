from http.server import BaseHTTPRequestHandler
import json
import os
import tempfile
import base64
import sys

import sys
import os

# Визначаємо шлях до директорії scripts відносно поточного файлу
current_dir = os.path.dirname(os.path.abspath(__file__))  # директорія api
parent_dir = os.path.dirname(current_dir)                 # коренева директорія
scripts_dir = os.path.join(parent_dir, "scripts")         # шлях до scripts

# Додаємо шлях до scripts у sys.path
sys.path.append(scripts_dir)

# Тепер імпортуємо модулі з директорії scripts

from scripts.html_converter import convert_html_to_scorm
from scripts.pdf_converter import convert_pdf_to_scorm



class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Отримуємо дані запиту
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))

        # Перевіряємо тип файлу
        file_type = data.get('file_type', '').lower()
        file_content_base64 = data.get('file_content', '')
        file_name = data.get('file_name', 'document')
        title = data.get('title', '')
        scorm_version = data.get('scorm_version', '2004')

        # Декодуємо вміст файлу
        try:
            file_content = base64.b64decode(file_content_base64)
        except:
            self.send_error(400, "Невірний формат файлу (Base64)")
            return

        # Створюємо тимчасовий файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as temp_file:
            temp_file.write(file_content)
            input_path = temp_file.name

        # Визначаємо шлях для виходу
        output_path = os.path.join(tempfile.gettempdir(), f"{file_name}_scorm.zip")

        # Вибираємо конвертер залежно від типу файлу
        result = False
        if file_type == 'html' or file_type == 'htm':
            result = convert_html_to_scorm(
                input_path,
                output_path=output_path,
                title=title,
                scorm_version=scorm_version
            )
        elif file_type == 'pdf':
            result = convert_pdf_to_scorm(
                input_path,
                output_path=output_path,
                title=title,
                scorm_version=scorm_version
            )
        else:
            self.send_error(400, f"Непідтримуваний тип файлу: {file_type}")
            os.unlink(input_path)
            return

        # Перевіряємо результат конвертації
        if not result or not os.path.exists(output_path):
            self.send_error(500, "Помилка конвертації")
            os.unlink(input_path)
            return

        # Зчитуємо згенерований SCORM-пакет
        with open(output_path, 'rb') as f:
            scorm_content = f.read()

        # Кодуємо в Base64 для відправки
        scorm_base64 = base64.b64encode(scorm_content).decode('utf-8')

        # Відправляємо відповідь
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {
            'success': True,
            'scorm_package': scorm_base64,
            'file_name': f"{file_name}_scorm.zip"
        }
        self.wfile.write(json.dumps(response).encode())

        # Прибираємо тимчасові файли
        os.unlink(input_path)
        os.unlink(output_path)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()