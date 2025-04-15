import base64
import io
import json
import os
import zipfile
from datetime import datetime


# Спрощений обробник, який створює базовий SCORM-пакет без зовнішніх залежностей
def handler(request):
    # Відповіді API
    def api_response(status_code, body):
        return {
            "statusCode": status_code,
            "body": json.dumps(body),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        }

    # Обробка OPTIONS для CORS
    if request.method == "OPTIONS":
        return api_response(200, {"message": "CORS OK"})

    # Перевіряємо метод
    if request.method != "POST":
        return api_response(405, {"error": "Method not allowed. Use POST instead."})

    try:
        # Отримуємо дані з запиту
        if isinstance(request.body, bytes):
            body = json.loads(request.body.decode('utf-8'))
        else:
            body = json.loads(request.body)

        # Отримуємо параметри
        file_type = body.get('file_type', '').lower()
        file_content_base64 = body.get('file_content', '')
        file_name = body.get('file_name', 'document')
        title = body.get('title', file_name)
        scorm_version = body.get('scorm_version', '2004')

        # Тимчасово відключаємо PDF
        if file_type == 'pdf':
            return api_response(200, {"error": "PDF conversion temporarily disabled"})

        # Перевіряємо підтримуваний тип файлу
        if file_type not in ['html', 'htm']:
            return api_response(400, {"error": f"Unsupported file type: {file_type}"})

        # Декодуємо base64
        try:
            file_content = base64.b64decode(file_content_base64)
        except:
            return api_response(400, {"error": "Invalid Base64 data"})

        # Перевіряємо розмір файлу
        if len(file_content) > 10 * 1024 * 1024:
            return api_response(400, {"error": "File too large. Max 10MB"})

        # Створюємо SCORM-пакет безпосередньо в пам'яті
        try:
            # Створюємо ZIP файл
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Додаємо основний HTML файл
                zipf.writestr(f"resources/{file_name}.html", file_content)

                # Створюємо обгортку для SCORM
                index_html = create_scorm_wrapper(title, f"{file_name}.html")
                zipf.writestr("index.html", index_html)

                # Створюємо JS файл для SCORM API
                js_content = create_scorm_api_js(scorm_version)
                zipf.writestr("scorm_api.js", js_content)

                # Створюємо маніфест SCORM
                manifest_content = create_scorm_manifest(title, file_name, scorm_version)
                zipf.writestr("imsmanifest.xml", manifest_content)

            # Отримуємо байти ZIP і кодуємо в base64
            zip_buffer.seek(0)
            zip_data = zip_buffer.getvalue()
            scorm_base64 = base64.b64encode(zip_data).decode('utf-8')

            # Успішна відповідь
            return api_response(200, {
                "success": True,
                "scorm_package": scorm_base64,
                "file_name": f"{file_name}_scorm.zip"
            })

        except Exception as e:
            return api_response(500, {
                "error": f"Error creating SCORM package: {str(e)}"
            })

    except Exception as e:
        return api_response(500, {
            "error": f"Server error: {str(e)}"
        })


# Функція для створення обгортки SCORM
def create_scorm_wrapper(title, html_filename):
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="scorm_api.js"></script>
    <style>
        body, html {{
            margin: 0;
            padding: 0;
            height: 100%;
            overflow: hidden;
            font-family: Arial, sans-serif;
        }}
        #content-container {{
            width: 100%;
            height: 100%;
            overflow: hidden;
        }}
        #content-frame {{
            width: 100%;
            height: 100%;
            border: none;
        }}
    </style>
</head>
<body onload="initializeSCORM();" onunload="terminateSCORM();">
    <div id="content-container">
        <iframe id="content-frame" src="resources/{html_filename}"></iframe>
    </div>
    <script>
        function initializeSCORM() {{
            if (typeof SCORM !== 'undefined') {{
                SCORM.init();
                SCORM.setCompletionStatus('incomplete');
            }}
        }}

        function terminateSCORM() {{
            if (typeof SCORM !== 'undefined') {{
                SCORM.terminate();
            }}
        }}
    </script>
</body>
</html>'''


# Функція для створення спрощеного SCORM API JavaScript
def create_scorm_api_js(scorm_version):
    return '''// Спрощена обгортка для SCORM API
var SCORM = {
    initialized: false,
    apiHandle: null,
    version: null,

    // Ініціалізація SCORM API
    init: function() {
        this.apiHandle = this.getAPI();
        if (this.apiHandle) {
            if (typeof this.apiHandle.Initialize !== 'undefined') {
                this.version = '2004';
                this.initialized = this.apiHandle.Initialize('');
            } else if (typeof this.apiHandle.LMSInitialize !== 'undefined') {
                this.version = '1.2';
                this.initialized = this.apiHandle.LMSInitialize('');
            }
        }
        return this.initialized;
    },

    // Завершення сесії
    terminate: function() {
        if (!this.initialized) return false;

        var result = false;
        try {
            if (this.version === '2004') {
                result = this.apiHandle.Terminate('');
            } else if (this.version === '1.2') {
                result = this.apiHandle.LMSFinish('');
            }
        } catch (e) {
            result = false;
        }

        this.initialized = false;
        return result;
    },

    // Застосування змін
    commit: function() {
        if (!this.initialized) return false;

        try {
            if (this.version === '2004') {
                return this.apiHandle.Commit('');
            } else if (this.version === '1.2') {
                return this.apiHandle.LMSCommit('');
            }
        } catch (e) {
            return false;
        }
    },

    // Встановлення статусу завершення
    setCompletionStatus: function(status) {
        if (!this.initialized) return false;

        try {
            if (this.version === '2004') {
                return this.apiHandle.SetValue('cmi.completion_status', status);
            } else if (this.version === '1.2') {
                var mappedStatus = {
                    'completed': 'completed',
                    'incomplete': 'incomplete',
                    'not attempted': 'not attempted'
                }[status] || 'incomplete';
                return this.apiHandle.LMSSetValue('cmi.core.lesson_status', mappedStatus);
            }
        } catch (e) {
            return false;
        }
    },

    // Пошук API в ієрархії фреймів
    getAPI: function() {
        var win = window;
        var foundAPI = null;

        // Пошук API у поточному вікні
        if (win.API_1484_11) return win.API_1484_11;
        if (win.API) return win.API;

        // Пошук API в батьківських вікнах
        while (win.parent !== win) {
            win = win.parent;
            if (win.API_1484_11) return win.API_1484_11;
            if (win.API) return win.API;
        }

        return null;
    }
};

// Глобальні функції для виклику з HTML
function initializeSCORM() {
    SCORM.init();
}

function terminateSCORM() {
    SCORM.terminate();
}'''


# Функція для створення спрощеного маніфесту SCORM
def create_scorm_manifest(title, file_name, scorm_version):
    # Створюємо унікальний ідентифікатор курсу
    course_id = f"COURSE_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if scorm_version == '1.2':
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="MANIFEST-{course_id}" version="1.0"
          xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
          xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                              http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
    <metadata>
        <schema>ADL SCORM</schema>
        <schemaversion>1.2</schemaversion>
    </metadata>
    <organizations default="default_org">
        <organization identifier="default_org">
            <title>{title}</title>
            <item identifier="item_1" identifierref="resource_1" isvisible="true">
                <title>{title}</title>
            </item>
        </organization>
    </organizations>
    <resources>
        <resource identifier="resource_1" type="webcontent" href="index.html" adlcp:scormtype="sco">
            <file href="index.html"/>
            <file href="scorm_api.js"/>
            <file href="resources/{file_name}.html"/>
        </resource>
    </resources>
</manifest>'''
    else:  # SCORM 2004
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="MANIFEST-{course_id}" version="1.0"
          xmlns="http://www.imsglobal.org/xsd/imscp_v1p1"
          xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_v1p3"
          xmlns:adlseq="http://www.adlnet.org/xsd/adlseq_v1p3"
          xmlns:adlnav="http://www.adlnet.org/xsd/adlnav_v1p3"
          xmlns:imsss="http://www.imsglobal.org/xsd/imsss"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://www.imsglobal.org/xsd/imscp_v1p1 imscp_v1p1.xsd
                              http://www.adlnet.org/xsd/adlcp_v1p3 adlcp_v1p3.xsd
                              http://www.adlnet.org/xsd/adlseq_v1p3 adlseq_v1p3.xsd
                              http://www.adlnet.org/xsd/adlnav_v1p3 adlnav_v1p3.xsd
                              http://www.imsglobal.org/xsd/imsss imsss_v1p0.xsd">
    <metadata>
        <schema>ADL SCORM</schema>
        <schemaversion>2004 4th Edition</schemaversion>
    </metadata>
    <organizations default="default_org">
        <organization identifier="default_org">
            <title>{title}</title>
            <item identifier="item_1" identifierref="resource_1">
                <title>{title}</title>
            </item>
        </organization>
    </organizations>
    <resources>
        <resource identifier="resource_1" type="webcontent" href="index.html" adlcp:scormType="sco">
            <file href="index.html"/>
            <file href="scorm_api.js"/>
            <file href="resources/{file_name}.html"/>
        </resource>
    </resources>
</manifest>'''