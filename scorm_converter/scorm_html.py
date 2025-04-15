#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import zipfile
import tempfile
import shutil
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from bs4 import BeautifulSoup
import re
import base64


def convert_scorm_to_html(scorm_path, output_path=None, output_dir=None, single_file=False):
    """
    Конвертує SCORM-пакет у HTML-формат

    Args:
        scorm_path (str): Шлях до SCORM-пакету (.zip)
        output_path (str): Шлях для збереження об'єднаного HTML-файлу (якщо single_file=True)
        output_dir (str): Директорія для збереження HTML-файлів і ресурсів
        single_file (bool): Об'єднати всі сторінки в один HTML-файл

    Returns:
        str: Шлях до створеного HTML-файлу або директорії
    """
    try:
        # Визначення вихідної директорії, якщо не вказано
        if not output_dir and not single_file:
            output_dir = os.path.splitext(scorm_path)[0] + "_html"
        elif not output_dir and single_file:
            output_dir = os.path.dirname(output_path) or '.'

        # Створення директорії, якщо не існує
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Створення тимчасової директорії для розпакування
        temp_dir = tempfile.mkdtemp()

        # Розпакування SCORM-пакету
        print(f"Розпакування SCORM-пакету: {scorm_path}")
        with zipfile.ZipFile(scorm_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Аналіз структури SCORM-пакету
        print("Аналіз структури SCORM-пакету...")
        scorm_content = analyze_scorm_package(temp_dir)

        if single_file:
            # Створення об'єднаного HTML-документу
            if not output_path:
                output_name = os.path.splitext(os.path.basename(scorm_path))[0]
                output_path = os.path.join(output_dir, f"{output_name}.html")

            print(f"Створення об'єднаного HTML-документу: {output_path}")
            combined_html = create_combined_html(temp_dir, scorm_content)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(combined_html)

            print(f"Успішно створено HTML: {output_path}")
            result_path = output_path
        else:
            # Копіювання всіх HTML-файлів і ресурсів
            print(f"Копіювання файлів у директорію: {output_dir}")
            html_files = extract_scorm_content(temp_dir, output_dir, scorm_content)

            # Створення індексного файлу для навігації
            index_path = create_index_html(output_dir, scorm_content, html_files)

            print(f"Успішно створено HTML-файли в: {output_dir}")
            print(f"Головний файл: {index_path}")
            result_path = output_dir

        # Очищення тимчасових файлів
        shutil.rmtree(temp_dir)

        return result_path

    except Exception as e:
        print(f"Помилка при конвертації SCORM в HTML: {e}")
        # Спроба очистити тимчасові файли у випадку помилки
        try:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
        return None


def analyze_scorm_package(scorm_dir):
    """
    Аналізує структуру SCORM-пакету і створює список контенту

    Args:
        scorm_dir (str): Директорія з розпакованим SCORM-пакетом

    Returns:
        dict: Інформація про вміст SCORM-пакету
    """
    content_info = {
        'title': 'SCORM Course',
        'pages': []
    }

    # Пошук маніфесту
    manifest_path = os.path.join(scorm_dir, 'imsmanifest.xml')

    if os.path.exists(manifest_path):
        # Парсинг маніфесту
        try:
            content_info.update(parse_scorm_manifest(manifest_path, scorm_dir))
        except Exception as e:
            print(f"Помилка при парсингу маніфесту: {e}")

    # Якщо маніфест не допоміг, шукаємо HTML-файли вручну
    if not content_info['pages']:
        html_files = []
        index_html = None

        for root, dirs, files in os.walk(scorm_dir):
            for file in files:
                if file.lower().endswith('.html') or file.lower().endswith('.htm'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, scorm_dir)

                    # Перевіряємо чи це головний HTML файл
                    if file.lower() == 'index.html' and root == scorm_dir:
                        index_html = rel_path

                    html_files.append(rel_path)

        # Спочатку додаємо index.html, якщо він є
        if index_html:
            content_info['pages'].append({
                'title': 'Main Page',
                'file': index_html,
                'type': 'html'
            })
            html_files.remove(index_html)

        # Додаємо інші HTML-файли
        for html_file in html_files:
            title = os.path.splitext(os.path.basename(html_file))[0]
            content_info['pages'].append({
                'title': title,
                'file': html_file,
                'type': 'html'
            })

    return content_info


def parse_scorm_manifest(manifest_path, scorm_dir):
    """
    Парсинг маніфесту SCORM для отримання структури контенту

    Args:
        manifest_path (str): Шлях до файлу imsmanifest.xml
        scorm_dir (str): Директорія з розпакованим SCORM-пакетом

    Returns:
        dict: Інформація про вміст SCORM-пакету
    """
    content_info = {
        'title': 'SCORM Course',
        'pages': []
    }

    tree = ET.parse(manifest_path)
    root = tree.getroot()

    # Визначення простору імен (для SCORM 2004 або 1.2)
    ns_cp = '{http://www.imsglobal.org/xsd/imscp_v1p1}'
    ns_adlcp = '{http://www.adlnet.org/xsd/adlcp_v1p3}'

    # Перевірка SCORM 1.2
    if 'xmlns' in root.attrib and 'http://www.imsproject.org/xsd/imscp_rootv1p1p2' in root.attrib['xmlns']:
        ns_cp = ''
        ns_adlcp = '{http://www.adlnet.org/xsd/adlcp_rootv1p2}'

    # Отримання загального заголовку курсу
    org_title = root.find(f'.//{ns_cp}organization/{ns_cp}title')
    if org_title is not None and org_title.text:
        content_info['title'] = org_title.text

    # Створення словника ресурсів
    resources = {}
    for resource in root.findall(f'.//{ns_cp}resource'):
        resource_id = resource.get('identifier')
        resource_type = resource.get('type')
        resource_href = resource.get('href')

        resources[resource_id] = {
            'type': resource_type,
            'href': resource_href,
            'files': []
        }

        # Збір файлів, пов'язаних з ресурсом
        for file_elem in resource.findall(f'.//{ns_cp}file'):
            file_href = file_elem.get('href')
            if file_href:
                resources[resource_id]['files'].append(file_href)

    # Проходження по елементах item для отримання структури
    for item in root.findall(f'.//{ns_cp}item'):
        item_title = item.find(f'{ns_cp}title')
        item_title_text = item_title.text if item_title is not None else 'Untitled'

        # Отримання посилання на ресурс
        resource_id = item.get('identifierref')
        if resource_id and resource_id in resources:
            resource = resources[resource_id]
            resource_href = resource['href']

            if resource_href:
                file_path = os.path.join(scorm_dir, resource_href)

                # Якщо файл існує, визначаємо його тип
                if os.path.exists(file_path):
                    file_ext = os.path.splitext(file_path)[1].lower()

                    if file_ext in ['.html', '.htm']:
                        file_type = 'html'
                    elif file_ext == '.pdf':
                        file_type = 'pdf'
                    else:
                        file_type = 'other'

                    content_info['pages'].append({
                        'title': item_title_text,
                        'file': resource_href,
                        'type': file_type,
                        'resource_id': resource_id,
                        'files': resource['files']
                    })

    return content_info


def create_combined_html(scorm_dir, content_info):
    """
    Створює комбінований HTML-документ з усіх сторінок SCORM

    Args:
        scorm_dir (str): Директорія з розпакованим SCORM-пакетом
        content_info (dict): Інформація про вміст SCORM-пакету

    Returns:
        str: HTML-вміст об'єднаного документу
    """
    html_parts = []

    # Початок документу
    html_parts.append(f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{content_info['title']}</title>
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }}
        header {{
            background-color: #f5f5f5;
            padding: 15px;
            text-align: center;
            border-bottom: 1px solid #ddd;
        }}
        nav {{
            background-color: #f9f9f9;
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        main {{
            flex: 1;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
        }}
        .page {{
            margin-bottom: 30px;
            border-bottom: 1px dashed #ccc;
            padding-bottom: 20px;
        }}
        .page:last-child {{
            border-bottom: none;
        }}
        .page-title {{
            background-color: #f5f5f5;
            padding: 10px;
            border-radius: 5px;
            border-left: 5px solid #333;
            margin-bottom: 15px;
        }}
        footer {{
            background-color: #f5f5f5;
            padding: 10px;
            text-align: center;
            border-top: 1px solid #ddd;
        }}
        /* Навігаційне меню */
        #toc {{
            list-style-type: none;
            padding: 0;
            margin: 0;
        }}
        #toc li {{
            margin-bottom: 5px;
        }}
        #toc a {{
            text-decoration: none;
            color: #0066cc;
            display: inline-block;
            padding: 3px 10px;
        }}
        #toc a:hover {{
            background-color: #eee;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>{content_info['title']}</h1>
    </header>
    <nav>
        <h3>Зміст:</h3>
        <ul id="toc">
''')

    # Створення змісту
    for i, page in enumerate(content_info['pages']):
        page_title = page.get('title', f'Сторінка {i + 1}')
        html_parts.append(f'<li><a href="#page-{i + 1}">{page_title}</a></li>')

    html_parts.append('''        </ul>
    </nav>
    <main>
''')

    # Обробка кожної сторінки
    for i, page in enumerate(content_info['pages']):
        page_title = page.get('title', f'Сторінка {i + 1}')
        page_file = page.get('file', '')
        page_type = page.get('type', 'other')

        html_parts.append(f'<div class="page" id="page-{i + 1}">')
        html_parts.append(f'<h2 class="page-title">{page_title}</h2>')

        if page_type == 'html':
            # Обробка HTML-сторінки
            try:
                file_path = os.path.join(scorm_dir, page_file)
                if os.path.exists(file_path):
                    html_content = process_html_content(file_path, scorm_dir)
                    html_parts.append(html_content)
                else:
                    html_parts.append(f'<p>Файл не знайдено: {page_file}</p>')
            except Exception as e:
                html_parts.append(f'<p>Помилка обробки HTML: {e}</p>')

        elif page_type == 'pdf':
            # Для PDF файлів додаємо посилання
            pdf_path = os.path.join(scorm_dir, page_file)
            if os.path.exists(pdf_path):
                pdf_filename = os.path.basename(page_file)
                # Створюємо base64 для вбудовування PDF
                try:
                    with open(pdf_path, 'rb') as pdf_file:
                        pdf_data = base64.b64encode(pdf_file.read()).decode('utf-8')

                    html_parts.append(f'''
                    <div class="pdf-embed">
                        <p>PDF документ: {pdf_filename}</p>
                        <object data="data:application/pdf;base64,{pdf_data}" type="application/pdf" width="100%" height="600px">
                            <p>Ваш браузер не підтримує вбудовані PDF. 
                            <a href="data:application/pdf;base64,{pdf_data}" download="{pdf_filename}">Завантажити PDF</a>.</p>
                        </object>
                    </div>
                    ''')
                except Exception as e:
                    html_parts.append(f'<p>Помилка вбудовування PDF: {e}</p>')
                    html_parts.append(f'<p>PDF документ: {pdf_filename}</p>')
            else:
                html_parts.append(f'<p>Файл не знайдено: {page_file}</p>')

        else:
            # Інші типи файлів
            html_parts.append(f'<p>Вміст типу "{page_type}" не може бути відображено безпосередньо.</p>')

        html_parts.append('</div>')

    # Закінчення документу
    html_parts.append('''    </main>
    <footer>
        <p>Згенеровано з SCORM-пакету</p>
    </footer>
</body>
</html>''')

    return '\n'.join(html_parts)


def process_html_content(html_path, scorm_dir):
    """
    Обробляє HTML-вміст для об'єднаного документу

    Args:
        html_path (str): Шлях до HTML-файлу
        scorm_dir (str): Директорія з розпакованим SCORM-пакетом

    Returns:
        str: Оброблений HTML-вміст
    """
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html_content = f.read()

    # Парсимо HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Видаляємо скрипти, які можуть конфліктувати з основним документом
    for script in soup.find_all(['script']):
        script.decompose()

    # Видаляємо теги <head>, <html>, <body>
    if soup.head:
        soup.head.decompose()

    # Оновлюємо шляхи до зображень
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src and not src.startswith(('http://', 'https://', 'data:')):
            # Отримуємо повний шлях до зображення
            img_rel_path = os.path.normpath(os.path.join(os.path.dirname(html_path), src))
            img_rel_path = os.path.relpath(img_rel_path, scorm_dir)

            # Перевіряємо чи існує файл
            img_path = os.path.join(scorm_dir, img_rel_path)
            if os.path.exists(img_path):
                # Вбудовуємо зображення як base64
                try:
                    with open(img_path, 'rb') as img_file:
                        img_data = base64.b64encode(img_file.read()).decode('utf-8')

                    img_ext = os.path.splitext(img_path)[1].lower()
                    if img_ext in ['.jpg', '.jpeg']:
                        mime_type = 'image/jpeg'
                    elif img_ext == '.png':
                        mime_type = 'image/png'
                    elif img_ext == '.gif':
                        mime_type = 'image/gif'
                    elif img_ext == '.svg':
                        mime_type = 'image/svg+xml'
                    else:
                        mime_type = 'image/jpeg'  # За замовчуванням

                    img['src'] = f"data:{mime_type};base64,{img_data}"
                except Exception as e:
                    print(f"Помилка вбудовування зображення {img_path}: {e}")
            else:
                # Якщо файл не існує, видаляємо атрибут src
                del img['src']

    # Оновлюємо посилання на інші ресурси
    for a in soup.find_all('a'):
        href = a.get('href', '')
        if href and not href.startswith(('http://', 'https://', 'data:', '#', 'javascript:')):
            # Отримуємо повний шлях до файлу
            link_rel_path = os.path.normpath(os.path.join(os.path.dirname(html_path), href))
            link_rel_path = os.path.relpath(link_rel_path, scorm_dir)

            # Якщо це PDF, спробуємо вбудувати його як base64
            if link_rel_path.lower().endswith('.pdf'):
                link_path = os.path.join(scorm_dir, link_rel_path)
                if os.path.exists(link_path):
                    try:
                        with open(link_path, 'rb') as pdf_file:
                            pdf_data = base64.b64encode(pdf_file.read()).decode('utf-8')
                        a['href'] = f"data:application/pdf;base64,{pdf_data}"
                        a['download'] = os.path.basename(link_rel_path)
                    except Exception as e:
                        print(f"Помилка вбудовування PDF {link_path}: {e}")

    # Повертаємо вміст без тегів body і html
    content = soup.body
    if content:
        return str(content.decode_contents())
    return str(soup)


def extract_scorm_content(scorm_dir, output_dir, content_info):
    """
    Копіює всі HTML-файли і ресурси зі SCORM-пакету у вказану директорію

    Args:
        scorm_dir (str): Директорія з розпакованим SCORM-пакетом
        output_dir (str): Вихідна директорія
        content_info (dict): Інформація про вміст SCORM-пакету

    Returns:
        dict: Словник з шляхами до HTML-файлів
    """
    html_files = {}

    # Копіюємо специфічні файли з маніфесту
    for i, page in enumerate(content_info['pages']):
        page_file = page.get('file', '')
        page_type = page.get('type', '')
        page_id = f"page-{i + 1}"

        if page_file and os.path.exists(os.path.join(scorm_dir, page_file)):
            # Створюємо структуру директорій, якщо потрібно
            output_file = os.path.join(output_dir, page_file)
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Копіюємо файл
            shutil.copy2(os.path.join(scorm_dir, page_file), output_file)

            # Зберігаємо інформацію про HTML-файл
            if page_type == 'html':
                html_files[page_id] = {
                    'title': page.get('title', f'Сторінка {i + 1}'),
                    'path': page_file
                }

            # Копіюємо пов'язані файли, якщо вони вказані
            if 'files' in page and page['files']:
                for file_path in page['files']:
                    if file_path != page_file:  # Не копіюємо той самий файл двічі
                        src_file = os.path.join(scorm_dir, file_path)
                        if os.path.exists(src_file):
                            dst_file = os.path.join(output_dir, file_path)
                            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                            shutil.copy2(src_file, dst_file)

    # Копіюємо загальні ресурси (зображення, CSS, JS тощо)
    resource_extensions = ['.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.mp3', '.mp4', '.woff', '.woff2',
                           '.ttf', '.eot']

    for root, dirs, files in os.walk(scorm_dir):
        for file in files:
            if any(file.lower().endswith(ext) for ext in resource_extensions):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, scorm_dir)
                dst_path = os.path.join(output_dir, rel_path)

                # Створюємо директорії, якщо потрібно
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)

                # Копіюємо файл, якщо він ще не існує
                if not os.path.exists(dst_path):
                    shutil.copy2(file_path, dst_path)

    return html_files


def create_index_html(output_dir, content_info, html_files):
    """
    Створює індексний HTML-файл з навігацією

    Args:
        output_dir (str): Вихідна директорія
        content_info (dict): Інформація про вміст SCORM-пакету
        html_files (dict): Словник з шляхами до HTML-файлів

    Returns:
        str: Шлях до створеного індексного файлу
    """
    index_path = os.path.join(output_dir, 'index.html')

    # Створюємо HTML-документ
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{content_info['title']}</title>
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }}
        header {{
            background-color: #f5f5f5;
            padding: 15px;
            text-align: center;
            border-bottom: 1px solid #ddd;
        }}
        .container {{
            display: flex;
            flex: 1;
        }}
        nav {{
            background-color: #f9f9f9;
            padding: 15px;
            width: 250px;
            border-right: 1px solid #ddd;
        }}
        main {{
            flex: 1;
            padding: 0;
            margin: 0;
            display: flex;
        }}
        iframe {{
            flex: 1;
            border: none;
            width: 100%;
            height: 100%;
        }}
        footer {{
            background-color: #f5f5f5;
            padding: 10px;
            text-align: center;
            border-top: 1px solid #ddd;
        }}
        /* Навігаційне меню */
        #toc {{
            list-style-type: none;
            padding: 0;
            margin: 0;
        }}
        #toc li {{
            margin-bottom: 10px;
        }}
        #toc a {{
            text-decoration: none;
            color: #0066cc;
            display: block;
            padding: 8px 10px;
            border-radius: 4px;
        }}
        #toc a:hover, #toc a.active {{
            background-color: #e0e0e0;
        }}
        .description {{
            font-size: 0.9em;
            color: #666;
            margin-top: 20px;
            padding: 10px;
            background-color: #f5f5f5;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>{content_info['title']}</h1>
    </header>
    <div class="container">
        <nav>
            <h3>Зміст курсу:</h3>
            <ul id="toc">
'''

    # Додаємо пункти навігації
    first_page = None
    for i, page in enumerate(content_info['pages']):
        page_id = f"page-{i + 1}"
        page_title = page.get('title', f'Сторінка {i + 1}')

        if page_id in html_files:
            page_path = html_files[page_id]['path']
            if not first_page:
                first_page = page_path

            html_content += f'<li><a href="{page_path}" target="content-frame">{page_title}</a></li>\n'

    html_content += '''            </ul>
            <div class="description">
                <p>Цей HTML-контент створено з SCORM-пакету.</p>
                <p>Виберіть сторінку зі змісту, щоб переглянути її.</p>
            </div>
        </nav>
        <main>
            <iframe name="content-frame" id="content-frame" src="'''

    # Додаємо першу сторінку як початкову
    if first_page:
        html_content += first_page

    html_content += '''"></iframe>
        </main>
    </div>
    <footer>
        <p>Згенеровано з SCORM-пакету</p>
    </footer>
    <script>
        // Додаємо активний клас до поточного пункту меню
        document.addEventListener('DOMContentLoaded', function() {
            var links = document.querySelectorAll('#toc a');
            links.forEach(function(link) {
                link.addEventListener('click', function() {
                    links.forEach(function(l) { l.classList.remove('active'); });
                    this.classList.add('active');
                });
            });

            // Активуємо перший пункт
            if (links.length > 0) {
                links[0].classList.add('active');
            }
        });
    </script>
</body>
</html>'''

    # Записуємо індексний файл
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return index_path


def main():
    """
    Головна функція для конвертації SCORM в HTML
    """
    parser = argparse.ArgumentParser(description='Конвертація SCORM-пакету в HTML-формат')
    parser.add_argument('input_file', nargs='?', help='Шлях до SCORM-пакету (.zip)')
    parser.add_argument('--output', '-o', help='Шлях для збереження HTML-файлу (при -s)')
    parser.add_argument('--output-dir', '-d', help='Директорія для збереження HTML-файлів')
    parser.add_argument('--single', '-s', action='store_true', help='Створити один HTML-файл')

    args = parser.parse_args()

    # Якщо шлях до файлу не вказано через аргументи, запитуємо його
    if not args.input_file:
        print("=== SCORM TO HTML CONVERTER ===")
        print("Цей скрипт конвертує SCORM-пакети в HTML-формат\n")

        # Показуємо список файлів у поточній директорії
        current_files = [f for f in os.listdir('.') if os.path.isfile(f) and f.lower().endswith('.zip')]

        if current_files:
            print("Знайдено ZIP-файли в поточній директорії:")
            for i, file in enumerate(current_files, 1):
                print(f"{i}. {file}")
            print("\nВиберіть номер файлу або введіть повний шлях до файлу:")

            file_input = input("> ").strip()
            try:
                file_index = int(file_input) - 1
                if 0 <= file_index < len(current_files):
                    args.input_file = current_files[file_index]
                else:
                    args.input_file = file_input
            except ValueError:
                args.input_file = file_input
        else:
            args.input_file = input("Введіть шлях до SCORM-пакету (.zip): ").strip()

    # Перевірка наявності файлу
    while not os.path.exists(args.input_file):
        print(f"Помилка: Файл '{args.input_file}' не знайдено")
        args.input_file = input("Введіть правильний шлях до файлу: ").strip()
        # Якщо користувач ввів порожній рядок, виходимо
        if not args.input_file:
            print("Операцію скасовано.")
            sys.exit(0)

    # Перевірка розширення файлу
    if not args.input_file.lower().endswith('.zip'):
        print("Увага: Файл не має розширення .zip. Це може бути не SCORM-пакет.")
        confirm = input("Продовжити? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Операцію скасовано.")
            sys.exit(0)

    # Запитуємо додаткові параметри, якщо вони не вказані
    if not args.single and not args.output_dir:
        single_input = input("Створити один HTML-файл? (y/n) [n]: ").strip().lower()
        args.single = single_input == 'y'

    if args.single and not args.output:
        output_dir = os.path.dirname(args.input_file) or '.'
        output_name = os.path.splitext(os.path.basename(args.input_file))[0]
        default_output = os.path.join(output_dir, f"{output_name}.html")
        output_input = input(f"Шлях до вихідного HTML-файлу [{default_output}]: ").strip()
        args.output = output_input or default_output

    if not args.single and not args.output_dir:
        output_dir = os.path.splitext(args.input_file)[0] + "_html"
        output_input = input(f"Директорія для збереження HTML-файлів [{output_dir}]: ").strip()
        args.output_dir = output_input or output_dir

    print("\nПочинаю конвертацію SCORM в HTML...")

    # Викликаємо функцію конвертації
    result = convert_scorm_to_html(args.input_file, args.output, args.output_dir, args.single)

    if result:
        if args.single:
            print(f"\nУспішно створено HTML-файл: {args.output}")
        else:
            print(f"\nУспішно створено HTML-файли в директорії: {args.output_dir}")
            print(f"Відкрийте файл index.html, щоб переглянути вміст SCORM-пакету.")
    else:
        print("\nПомилка при конвертації SCORM в HTML")
        sys.exit(1)


if __name__ == "__main__":
    main()