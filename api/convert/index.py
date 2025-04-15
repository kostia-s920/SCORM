from http.server import BaseHTTPRequestHandler
import json


# Правильний формат для Vercel Python functions
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Встановлюємо статус і заголовки
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # Відправляємо тестову відповідь
        response = {
            "success": True,
            "message": "API works!"
        }
        self.wfile.write(json.dumps(response).encode())
        return


# Не змінюйте цей експорт - він важливий для Vercel
def handler(request, context):
    # Тестова функція, яка просто відповідає успіхом
    return {
        "statusCode": 200,
        "body": json.dumps({
            "success": True,
            "message": "API works!"
        }),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
    }