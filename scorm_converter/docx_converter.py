#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile
import shutil
import zipfile
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from datetime import datetime
from uuid import uuid4


def convert_docx_to_scorm(docx_path, output_path, title=None, scorm_version='2004'):
    """
    Конвертує DOCX-файл у SCORM-пакет

    Args:
        docx_path (str): Шлях до DOCX-файлу
        output_path (str): Шлях для збереження SCORM-пакету (.zip)
        title (str): Назва курсу (за замовчуванням - назва DOCX-файлу)
        scorm_version (str): Версія SCORM ('1.2' або '2004')

    Returns:
        bool: True у разі успіху, False - у разі помилки
    """
    try:
        # Створення тимчасової директорії для роботи
        temp_dir = tempfile.mkdtemp()
        content_dir = os.path.join(temp_dir, 'content')
        os.makedirs(content_dir, exist_ok=True)

        # Базові метадані
        if not title:
            title = os.path.splitext(os.path.basename(docx_path))[0]

        # Генерація ідентифікатора курсу
        course_id = str(uuid4())

        # Копіювання DOCX-файлу
        docx_filename = os.path.basename(docx_path)
        docx_dest_path = os.path.join(content_dir, docx_filename)
        shutil.copyfile(docx_path, docx_dest_path)

        # Створення простої HTML-сторінки для відображення DOCX
        html_content = create_simple_viewer(docx_filename, title)

        # Запис HTML-файлу
        html_path = os.path.join(content_dir, 'index.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Створення маніфесту SCORM
        create_scorm_manifest(content_dir, title, docx_filename, course_id, scorm_version)

        # Додавання JavaScript для SCORM API
        create_scorm_api_js(content_dir, scorm_version)

        # Створення ZIP-архіву
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(content_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(
                        file_path,
                        os.path.relpath(file_path, content_dir)
                    )

        # Очищення тимчасових файлів
        shutil.rmtree(temp_dir)

        return True
    except Exception as e:
        print(f"Помилка при конвертації DOCX в SCORM: {e}")
        # Спроба очистити тимчасові файли у випадку помилки
        try:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
        return False


def create_simple_viewer(docx_filename, title):
    """
    Створює просту HTML-сторінку для завантаження DOCX-файлу

    Args:
        docx_filename (str): Назва DOCX-файлу
        title (str): Заголовок сторінки

    Returns:
        str: HTML-вміст
    """
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="scorm_api.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            text-align: center;
        }}
        h1 {{
            color: #333;
            margin-bottom: 30px;
        }}
        .download-btn {{
            display: inline-block;
            background-color: #4CAF50;
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            font-size: 18px;
            border-radius: 4px;
            margin-top: 20px;
        }}
        .download-btn:hover {{
            background-color: #45a049;
        }}
        .info {{
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            margin-top: 30px;
            text-align: left;
        }}
    </style>
</head>
<body onload="initializeSCORM();" onunload="terminateSCORM();">
    <h1>{title}</h1>

    <p>Натисніть кнопку нижче, щоб завантажити документ:</p>

    <a href="{docx_filename}" download class="download-btn">Завантажити документ</a>

    <div class="info">
        <h3>Інформація про документ:</h3>
        <p><strong>Назва:</strong> {docx_filename}</p>
        <p><strong>Тип:</strong> Microsoft Word Document</p>
    </div>

    <script>
        // Відмічаємо як "переглянуто" після 10 секунд
        setTimeout(function() {{
            if (typeof SCORM !== 'undefined') {{
                SCORM.setCompletionStatus('completed');
            }}
        }}, 10000);
    </script>
</body>
</html>"""
    return html_content


def create_scorm_api_js(content_dir, scorm_version):
    """
    Створює JavaScript файл для взаємодії з SCORM API

    Args:
        content_dir (str): Директорія контенту
        scorm_version (str): Версія SCORM ('1.2' або '2004')
    """
    js_content = """// Спрощена обгортка для SCORM API
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

        if (this.version === '2004') {
            result = this.apiHandle.Terminate('');
        } else if (this.version === '1.2') {
            result = this.apiHandle.LMSFinish('');
        }

        this.initialized = false;
        return result;
    },

    // Встановлення статусу завершення
    setCompletionStatus: function(status) {
        if (!this.initialized) return false;

        if (this.version === '2004') {
            return this.apiHandle.SetValue('cmi.completion_status', status);
        } else if (this.version === '1.2') {
            var statusMap = {
                'completed': 'completed',
                'incomplete': 'incomplete',
                'not attempted': 'not attempted',
                'failed': 'failed',
                'passed': 'passed'
            };
            return this.apiHandle.LMSSetValue('cmi.core.lesson_status', statusMap[status] || 'incomplete');
        }

        return false;
    },

    // Встановлення прогресу проходження
    setProgressMeasure: function(progress) {
        if (!this.initialized) return false;

        if (this.version === '2004') {
            return this.apiHandle.SetValue('cmi.progress_measure', progress.toString());
        } else if (this.version === '1.2') {
            // SCORM 1.2 не має прямого відповідника для progress_measure
            // Можемо використати score як наближення
            return this.apiHandle.LMSSetValue('cmi.core.score.raw', Math.round(progress * 100).toString());
        }

        return false;
    },

    // Пошук API в ієрархії фреймів
    getAPI: function() {
        var win = window;
        var findAPITries = 0;
        var findAPIMaxTries = 10;

        // Спочатку шукаємо SCORM 2004 API
        while ((win.API_1484_11 == null) && (win.parent != null) && (win.parent != win) && (findAPITries < findAPIMaxTries)) {
            findAPITries++;
            win = win.parent;
        }

        if (win.API_1484_11) {
            return win.API_1484_11;
        }

        // Якщо не знайшли, шукаємо SCORM 1.2 API
        win = window;
        findAPITries = 0;

        while ((win.API == null) && (win.parent != null) && (win.parent != win) && (findAPITries < findAPIMaxTries)) {
            findAPITries++;
            win = win.parent;
        }

        return win.API || null;
    }
};

// Функції для виклику з HTML
function initializeSCORM() {
    SCORM.init();
    SCORM.setCompletionStatus('incomplete');
}

function terminateSCORM() {
    SCORM.terminate();
}
"""

    js_path = os.path.join(content_dir, 'scorm_api.js')
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)


def create_scorm_manifest(content_dir, title, docx_filename, course_id, scorm_version):
    """
    Створює маніфест SCORM

    Args:
        content_dir (str): Директорія контенту
        title (str): Назва курсу
        docx_filename (str): Назва DOCX-файлу
        course_id (str): Ідентифікатор курсу
        scorm_version (str): Версія SCORM ('1.2' або '2004')
    """
    manifest_path = os.path.join(content_dir, 'imsmanifest.xml')

    # Створення кореневого елемента маніфесту
    manifest = ET.Element('manifest')
    manifest.set('identifier', f"MANIFEST-{course_id}")
    manifest.set('version', '1.0')

    # Налаштування простору імен залежно від версії SCORM
    if scorm_version == '1.2':
        manifest.set('xmlns', 'http://www.imsproject.org/xsd/imscp_rootv1p1p2')
        manifest.set('xmlns:adlcp', 'http://www.adlnet.org/xsd/adlcp_rootv1p2')
        manifest.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        manifest.set('xsi:schemaLocation',
                     'http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd')
    else:  # SCORM 2004
        manifest.set('xmlns', 'http://www.imsglobal.org/xsd/imscp_v1p1')
        manifest.set('xmlns:adlcp', 'http://www.adlnet.org/xsd/adlcp_v1p3')
        manifest.set('xmlns:adlseq', 'http://www.adlnet.org/xsd/adlseq_v1p3')
        manifest.set('xmlns:adlnav', 'http://www.adlnet.org/xsd/adlnav_v1p3')
        manifest.set('xmlns:imsss', 'http://www.imsglobal.org/xsd/imsss')
        manifest.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        manifest.set('xsi:schemaLocation',
                     'http://www.imsglobal.org/xsd/imscp_v1p1 imscp_v1p1.xsd http://www.adlnet.org/xsd/adlcp_v1p3 adlcp_v1p3.xsd http://www.adlnet.org/xsd/adlseq_v1p3 adlseq_v1p3.xsd http://www.adlnet.org/xsd/adlnav_v1p3 adlnav_v1p3.xsd http://www.imsglobal.org/xsd/imsss imsss_v1p0.xsd')

    # Метадані
    metadata = ET.SubElement(manifest, 'metadata')
    schema = ET.SubElement(metadata, 'schema')
    schema.text = 'ADL SCORM'
    schemaversion = ET.SubElement(metadata, 'schemaversion')
    schemaversion.text = '1.2' if scorm_version == '1.2' else '2004 4th Edition'

    # Організація
    organizations = ET.SubElement(manifest, 'organizations')
    organizations.set('default', 'default_org')

    # Створення основної організації
    organization = ET.SubElement(organizations, 'organization')
    organization.set('identifier', 'default_org')

    org_title = ET.SubElement(organization, 'title')
    org_title.text = title

    # Створення елемента item
    item = ET.SubElement(organization, 'item')
    item.set('identifier', 'item_1')
    item.set('identifierref', 'resource_1')

    item_title = ET.SubElement(item, 'title')
    item_title.text = title

    # Ресурси
    resources = ET.SubElement(manifest, 'resources')

    # Створення основного ресурсу
    resource = ET.SubElement(resources, 'resource')
    resource.set('identifier', 'resource_1')
    resource.set('type', 'webcontent')
    resource.set('href', 'index.html')

    if scorm_version == '1.2':
        resource.set('adlcp:scormtype', 'sco')
    else:
        resource.set('adlcp:scormType', 'sco')

    # Додавання файлів
    files = ['index.html', 'scorm_api.js', docx_filename]
    for file in files:
        file_elem = ET.SubElement(resource, 'file')
        file_elem.set('href', file)

    # Форматування XML для кращої читабельності
    rough_string = ET.tostring(manifest, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(reparsed.toprettyxml(indent="  "))