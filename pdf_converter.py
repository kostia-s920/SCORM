#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Конвертер PDF в SCORM

Цей скрипт конв ертує PDF файли в пакети SCORM.
Використовує PyMuPDF для обробки PDF та створює SCORM пакет.
Версія зі спро щ еним вертикальним переглядом PDF.

Використання:
    python pdf_to_scorm.py input.pdf [--output output.zip] [--title "Назва курсу"]
    [--scorm-version 2004] [--extract-images]
"""

import argparse
import os
import tempfile
import shutil
import zipfile
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from datetime import datetime
from uuid import uuid4
import base64
import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup

try:
    import fitz  # PyMuPDF для роботи з PDF
except ImportError:
    print("Помилка: Необхідна бібліотека PyMuPDF (fitz) не встановлена")
    print("Встановіть її за допомогою команди: pip install PyMuPDF")
    sys.exit(1)


def convert_pdf_to_html(pdf_path, output_dir=None, extract_images=True, page_break=True):
    """
    Конвертує PDF у простий HTML з відображенням сторінок послідовно одна за одною
    для можливості простого прокручування

    Args:
        pdf_path (str): Шлях до PDF файлу
        output_dir (str): Директорія для збереження HTML та зображень
        extract_images (bool): Чи видобувати зображення з PDF
        page_break (bool): Чи додавати розриви сторінок між сторінками PDF

    Returns:
        tuple: (Шлях до HTML, словник з метаданими)
    """
    try:
        print(f"Конвертування PDF файлу: {pdf_path}")

        # Створюємо тимчасову директорію, якщо не вказана
        if not output_dir:
            output_dir = tempfile.mkdtemp()
            is_temp = True
        else:
            os.makedirs(output_dir, exist_ok=True)
            is_temp = False

        # Створюємо директорію для зображень
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)

        # Відкриваємо PDF
        doc = fitz.open(pdf_path)
        pdf_title = os.path.splitext(os.path.basename(pdf_path))[0]

        # Отримуємо метадані
        metadata = doc.metadata
        if metadata is None:
            metadata = {}

        # Створюємо HTML файл
        html_path = os.path.join(output_dir, 'index.html')

        # Генеруємо HTML вміст - максимально простий вертикальний перегляд PDF
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{metadata.get('title', pdf_title)}</title>
    <style>
        /* Базові стилі */
        body, html {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
        }}

        /* Контейнер для заголовка */
        #header {{
            background-color: #2c3e50;
            color: white;
            padding: 15px;
            position: sticky;
            top: 0;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            z-index: 100;
            text-align: center;
        }}

        #title {{
            margin: 0;
            font-size: 20px;
            font-weight: bold;
        }}

        #pageInfo {{
            font-size: 14px;
            margin-top: 5px;
        }}

        /* Контейнер для всіх сторінок */
        #pages-container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }}

        /* Контейнер для кожної сторінки */
        .page-container {{
            margin-bottom: 30px;
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        /* Заголовок сторінки */
        .page-header {{
            background-color: #f0f0f0;
            padding: 10px 15px;
            border-bottom: 1px solid #ddd;
            font-weight: bold;
        }}

        /* Зображення сторінки */
        .page-image {{
            width: 100%;
            height: auto;
            display: block;
        }}

        /* Нижній футер */
        #footer {{
            text-align: center;
            padding: 20px;
            color: #777;
            font-size: 12px;
            margin-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <!-- Заголовок -->
    <div id="header">
        <h1 id="title">{metadata.get('title', pdf_title)}</h1>
        <div id="pageInfo">PDF документ • {doc.page_count} сторінок</div>
    </div>

    <!-- Контейнер для всіх сторінок -->
    <div id="pages-container">
"""

        # Додаємо всі сторінки послідовно
        for page_num, page in enumerate(doc):
            print(f"Обробка сторінки {page_num + 1}/{doc.page_count}")

            # Створюємо зображення сторінки
            try:
                # Високоякісне зображення для відображення
                page_pixmap = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
                page_image_path = os.path.join(images_dir, f"page{page_num + 1}.png")
                page_pixmap.save(page_image_path)

                page_img_rel_path = f"images/page{page_num + 1}.png"
                html_content += f"""        <div class="page-container" id="page-{page_num + 1}" data-page="{page_num + 1}">
            <div class="page-header">Сторінка {page_num + 1}</div>
            <img src="{page_img_rel_path}" class="page-image" alt="Сторінка {page_num + 1}" 
                 onload="trackPageLoad({page_num + 1})" onerror="trackPageError({page_num + 1})">
        </div>
"""
                print(f"  Створено зображення сторінки {page_num + 1}, шлях: {page_image_path}")
            except Exception as e:
                print(f"Помилка при створенні зображення сторінки {page_num + 1}: {e}")
                html_content += f"""        <div class="page-container" id="page-{page_num + 1}" data-page="{page_num + 1}">
            <div class="page-header">Сторінка {page_num + 1}</div>
            <div style="padding: 20px; color: red;">Помилка завантаження сторінки {page_num + 1}</div>
        </div>
"""

        # Додаємо футер
        html_content += """    </div>

    <!-- Футер -->
    <div id="footer">
        Документ створено автоматичним конвертером PDF в SCORM
    </div>

    <script>
        // Глобальні змінні
        var totalPages = """ + str(doc.page_count) + """;
        var pagesLoaded = 0;
        var visiblePages = new Set();
        var startTime = Date.now();
        var lastScrollTime = Date.now();
        var lastProgressUpdate = 0;

        // Відстеження завантаження сторінок
        function trackPageLoad(pageNum) {
            pagesLoaded++;

            // Якщо всі сторінки завантажено, повідомляємо SCORM
            if (pagesLoaded === totalPages) {
                notifyParentWindow('documentLoaded', { 
                    totalPages: totalPages,
                    status: 'complete'
                });
            }
        }

        function trackPageError(pageNum) {
            // Порожній обробник помилок завантаження сторінки
        }

        // Визначення видимих сторінок
        function updateVisiblePages() {
            var pageContainers = document.querySelectorAll('.page-container');
            var viewportTop = window.scrollY;
            var viewportBottom = viewportTop + window.innerHeight;
            var currentVisiblePages = new Set();

            pageContainers.forEach(function(container) {
                var rect = container.getBoundingClientRect();
                var elementTop = rect.top + window.scrollY;
                var elementBottom = elementTop + rect.height;
                var isVisible = elementBottom > viewportTop && elementTop < viewportBottom;

                if (isVisible) {
                    var pageNum = parseInt(container.getAttribute('data-page'), 10);
                    currentVisiblePages.add(pageNum);

                    // Якщо сторінка стала видимою вперше
                    if (!visiblePages.has(pageNum)) {
                        // Повідомляємо SCORM про зміну сторінки
                        notifyParentWindow('pageChanged', {
                            currentPage: pageNum,
                            totalPages: totalPages
                        });
                    }
                }
            });

            // Оновлюємо набір видимих сторінок
            visiblePages = currentVisiblePages;
        }

        // Функція оновлення прогресу на основі прокрутки
        function updateProgress() {
            // Отримуємо поточний час
            var now = Date.now();
            lastScrollTime = now;

            // Визначаємо яку частину документа прокручено
            var scrollTop = window.scrollY;
            var windowHeight = window.innerHeight;
            var docHeight = document.body.offsetHeight;

            // Визначаємо відсоток прокрутки (0-100)
            var scrollPercent = Math.min(100, Math.max(0, Math.round(
                (scrollTop / (docHeight - windowHeight)) * 100
            )));

            // Запобігаємо надмірним оновленням (оновлюємо лише якщо зміна більше 2% або минуло 3 секунди)
            if (Math.abs(scrollPercent - lastProgressUpdate) > 2 || (now - startTime) % 3000 < 100) {
                lastProgressUpdate = scrollPercent;

                // Повідомляємо SCORM про прогрес
                notifyParentWindow('updateProgress', {
                    scrollPercent: scrollPercent,
                    totalPages: totalPages,
                    timeSpent: Math.floor((now - startTime) / 1000)
                });

                // Оновлюємо інформацію про видимі сторінки
                updateVisiblePages();
            }
        }

        // Відправка повідомлень до батьківського вікна (SCORM)
        function notifyParentWindow(action, data) {
            if (window.parent && window.parent !== window) {
                var message = Object.assign({ action: action, timestamp: Date.now() }, data);
                try {
                    window.parent.postMessage(message, '*');
                } catch (e) {
                    // Помилки обробляються тихо
                }
            }
        }

        // Ініціалізація при завантаженні документа
        document.addEventListener('DOMContentLoaded', function() {
            // Відправляємо початкове повідомлення про завантаження
            notifyParentWindow('documentLoaded', { 
                totalPages: totalPages,
                status: 'initializing'
            });

            // Встановлюємо відстеження прокрутки з дебаунсингом
            var scrollTimer;
            window.addEventListener('scroll', function() {
                // Відміняємо попередній таймер
                clearTimeout(scrollTimer);

                // Встановлюємо новий таймер (50мс дебаунсинг)
                scrollTimer = setTimeout(updateProgress, 50);
            });

            // Встановлюємо відстеження розміру вікна
            window.addEventListener('resize', updateProgress);

            // Періодично оновлюємо прогрес кожні 10 секунд навіть без прокрутки
            setInterval(function() {
                // Перевіряємо, чи була прокрутка за останні 10 секунд
                var now = Date.now();
                if (now - lastScrollTime > 10000) {
                    updateProgress();
                }
            }, 10000);

            // Початковий прогрес
            setTimeout(updateProgress, 500);

            // Приймаємо повідомлення від батьківського вікна
            window.addEventListener('message', function(event) {
                if (event.data && event.data.action === 'ping') {
                    // Відповідаємо на ping
                    notifyParentWindow('pong', { to: event.data.from });
                }
            });
        });
    </script>
</body>
</html>
"""

        # Зберігаємо HTML файл
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"HTML файл створено: {html_path}")

        return (html_path, {
            'title': metadata.get('title', pdf_title),
            'author': metadata.get('author', 'Не вказано'),
            'pages': doc.page_count,
            'images_dir': images_dir,
            'output_dir': output_dir,
            'is_temp': is_temp
        })

    except Exception as e:
        print(f"Помилка при конвертації PDF в HTML: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def process_html_file(html_path, content_dir, resources_dir, include_resources=True):
    """
    Обробляє HTML-файл та копіює пов'язані ресурси
    """
    print(f"Почато обробку HTML-файлу: {html_path}")
    print(f"Директорія контенту: {content_dir}")
    print(f"Директорія ресурсів: {resources_dir}")
    print(f"Включення ресурсів: {include_resources}")

    resources = {
        'html': [],
        'css': [],
        'js': [],
        'images': [],
        'fonts': [],
        'other': []
    }

    # Копіювання HTML-файлу
    html_filename = os.path.basename(html_path)
    html_dest = os.path.join(resources_dir, html_filename)
    print(f"Копіювання HTML-файлу з {html_path} в {html_dest}")

    try:
        # Читаємо HTML-вміст
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        print(f"Успішно прочитано HTML-файл довжиною {len(html_content)} символів")

        # Парсимо HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        print("HTML успішно розібрано за допомогою BeautifulSoup")

        # Обробка для локальних ресурсів
        if include_resources:
            # Обробка локальних зображень
            images = soup.find_all('img')
            print(f"Знайдено {len(images)} зображень")

            for img in images:
                src = img.get('src')
                if src and not src.startswith(('http://', 'https://', 'data:', '//')):
                    original_path = os.path.normpath(os.path.join(os.path.dirname(html_path), src))
                    print(f"Обробка зображення: {src} -> {original_path}")

                    if os.path.exists(original_path) and os.path.isfile(original_path):
                        # Створюємо структуру директорій, якщо потрібно
                        rel_dir = os.path.dirname(src)
                        if rel_dir:
                            os.makedirs(os.path.join(resources_dir, rel_dir), exist_ok=True)

                        # Копіюємо файл, але перевіряємо чи не є це тим самим файлом
                        dest_file = os.path.join(resources_dir, src)

                        # Перевіряємо чи не копіюємо файл сам у себе
                        if os.path.abspath(original_path) == os.path.abspath(dest_file):
                            print(f"  Пропускаємо копіювання {original_path} - файл вже знаходиться в потрібному місці")
                        else:
                            print(f"  Копіювання {original_path} в {dest_file}")
                            shutil.copy2(original_path, dest_file)

                        resources['images'].append(src)
                    else:
                        print(f"  Файл {original_path} не існує або не є файлом")

        # Додаємо meta тег для запобігання зовнішніх запитів
        head = soup.find('head')
        if head:
            meta_csp = soup.new_tag('meta')
            meta_csp['http-equiv'] = 'Content-Security-Policy'
            meta_csp[
                'content'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
            head.insert(0, meta_csp)
            print("Додано Content-Security-Policy для захисту від зовнішніх запитів")

        # Зберігаємо оновлений HTML-вміст
        print(f"Збереження оновленого HTML в {html_dest}")
        with open(html_dest, 'w', encoding='utf-8') as f:
            f.write(str(soup))

        # Додаємо HTML до списку ресурсів
        resources['html'].append(html_filename)
        print(f"Додано HTML-файл {html_filename} до списку ресурсів")

    except Exception as e:
        # Перевіряємо чи це помилка копіювання того самого файлу
        if isinstance(e, shutil.SameFileError):
            print(f"Попередження: {e}")
            print("Пропускаємо спробу копіювання файлу самого в себе")

            # Якщо файл HTML вже існує, просто додаємо його до списку ресурсів
            if os.path.exists(html_dest):
                resources['html'].append(html_filename)
                print(f"Використовуємо вже наявний HTML-файл: {html_filename}")

                # Також шукаємо всі зображення в директорії
                for img_dir, _, files in os.walk(os.path.join(resources_dir, 'images')):
                    for file in files:
                        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                            img_rel_path = os.path.join('images', file)
                            resources['images'].append(img_rel_path)
                            print(f"  Додано зображення до ресурсів: {img_rel_path}")
            else:
                # На випадок якщо файл не існує, створюємо запасний варіант
                create_fallback_html(html_dest, resources)
        else:
            print(f"Помилка при обробці HTML-файлу: {e}")
            import traceback
            traceback.print_exc()

            # Шукаємо всі зображення в директорії
            pdf_info = {'pages': 0}
            if os.path.exists(os.path.join(resources_dir, 'images')):
                # Підраховуємо кількість сторінок за зображеннями
                page_count = 0
                for img_dir, _, files in os.walk(os.path.join(resources_dir, 'images')):
                    for file in files:
                        if file.lower().startswith('page') and file.lower().endswith('.png'):
                            page_num = 0
                            try:
                                # Extracting page number from filenames like "page1.png"
                                page_num = int(file.lower().replace('page', '').split('.')[0])
                                page_count = max(page_count, page_num)
                            except:
                                pass

                            img_rel_path = os.path.join('images', file)
                            resources['images'].append(img_rel_path)
                            print(f"  Додано зображення до ресурсів: {img_rel_path}")

                pdf_info['pages'] = page_count

            # Створюємо замість проблемного HTML простий чистий HTML без зовнішніх ресурсів
            create_fallback_html(html_dest, resources, pdf_info)

    print("Завершено обробку HTML-файлу")
    return resources


def create_fallback_html(html_dest, resources, pdf_info=None):
    """Створює запасний простий HTML-файл у випадку помилки"""
    # Базова інформація про PDF, якщо доступна
    pdf_title = "PDF документ"
    author = "Невідомий"
    pages = 0

    if pdf_info:
        pdf_title = pdf_info.get('title', "PDF документ")
        author = pdf_info.get('author', "Невідомий")
        pages = pdf_info.get('pages', 0)

    # Створюємо HTML з посиланнями на зображення сторінок, якщо вони існують
    pages_html = ""
    images_dir = os.path.dirname(html_dest)

    # Перевіряємо наявність зображень сторінок
    for i in range(1, pages + 1):
        img_path = os.path.join(images_dir, f"images/page{i}.png")
        rel_path = f"images/page{i}.png"

        if os.path.exists(img_path):
            pages_html += f"""
            <div class="page-container">
                <div class="page-header">Сторінка {i}</div>
                <img src="{rel_path}" alt="Сторінка {i}" class="page-image">
            </div>
            """

    # Якщо не знайдено жодного зображення сторінки
    if not pages_html:
        pages_html = "<p>Не вдалося витягнути зображення сторінок з PDF файлу.</p>"

    clean_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{pdf_title}</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}

        #header {{
            background-color: #2c3e50;
            color: white;
            padding: 15px;
            text-align: center;
        }}

        h1 {{ 
            margin: 0;
            font-size: 20px;
            font-weight: bold;
        }}

        #pageInfo {{
            font-size: 14px;
            margin-top: 5px;
        }}

        #pages-container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }}

        .page-container {{
            margin-bottom: 30px;
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .page-header {{
            background-color: #f0f0f0;
            padding: 10px 15px;
            border-bottom: 1px solid #ddd;
            font-weight: bold;
        }}

        .page-image {{
            width: 100%;
            height: auto;
            display: block;
        }}

        .metadata {{
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}

        #footer {{
            text-align: center;
            padding: 20px;
            color: #777;
            font-size: 12px;
            margin-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div id="header">
        <h1>{pdf_title}</h1>
        <div id="pageInfo">PDF документ • {pages} сторінок</div>
    </div>

    <div id="pages-container">
        <div class="metadata">
            <p><strong>Автор:</strong> {author}</p>
            <p><strong>Кількість сторінок:</strong> {pages}</p>
        </div>

        {pages_html}
    </div>

    <div id="footer">
        Документ створено автоматичним конвертером PDF в SCORM
    </div>
</body>
</html>"""

    html_filename = os.path.basename(html_dest)
    with open(html_dest, 'w', encoding='utf-8') as f:
        f.write(clean_html)

    resources['html'].append(html_filename)
    print(f"Створено HTML-файл з переглядом сторінок")

    return resources


def create_scorm_wrapper(content_dir, title, html_filename, html_files):
    """
    Створює безпечну HTML-обгортку для SCORM
    """
    index_path = os.path.join(content_dir, 'index.html')

    # Очищення title від потенційно небезпечних HTML-тегів
    title = BeautifulSoup(title, "html.parser").get_text()

    # Створення HTML-обгортки для SCORM з максимальним захистом від зовнішніх запитів
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; frame-src 'self';">
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
<body onload="initSCORM();">
    <div id="content-container">
        <iframe id="content-frame" src="resources/{html_filename}" sandbox="allow-same-origin allow-scripts allow-forms"></iframe>
    </div>

    <script>
        // Глобальні змінні для відстеження
        var sessionStartTime = new Date();
        var timeSpent = 0;
        var completed = false;
        var scrollProgress = 0;
        var currentPage = 1;
        var totalPages = 0;

        // Елементи DOM
        var contentFrame = document.getElementById('content-frame');

        // Ініціалізація SCORM при завантаженні сторінки
        function initSCORM() {{
            // Викликаємо глобальну функцію ініціалізації
            initializeSCORM();

            // Слухаємо повідомлення від iframe
            setupMessageListener();

            // Починаємо періодичне оновлення даних
            startPeriodicUpdates();

            // Додаємо обробник події перед закриттям сторінки
            window.addEventListener('beforeunload', function(e) {{
                terminateSCORM();
            }});
        }}

        // Налаштування прослуховувача повідомлень від iframe
        function setupMessageListener() {{
            window.addEventListener('message', function(event) {{
                // Перевіряємо чи повідомлення від нашого iframe
                if (event.source === contentFrame.contentWindow) {{
                    if (event.data) {{
                        // Обробка різних типів повідомлень
                        switch(event.data.action) {{
                            case 'documentLoaded':
                                handleDocumentLoaded(event.data);
                                break;

                            case 'updateProgress':
                                handleProgressUpdate(event.data);
                                break;

                            case 'pageChanged':
                                handlePageChange(event.data);
                                break;
                        }}
                    }}
                }}
            }});

            // Також відправляємо повідомлення до iframe, щоб перевірити з'єднання
            setTimeout(function() {{
                try {{
                    contentFrame.contentWindow.postMessage({{'action': 'ping', 'from': 'scorm-wrapper'}}, '*');
                }} catch(e) {{
                    // Тиха обробка помилок
                }}
            }}, 1000);
        }}

        // Обробка завантаження документа
        function handleDocumentLoaded(data) {{
            totalPages = data.totalPages || 1;

            // Встановлюємо початковий прогрес та статус
            if (typeof updateSCORMProgress === 'function') {{
                updateSCORMProgress(0.01, '1');
            }}

            // Також оновлюємо через основний API для сумісності
            if (typeof SCORM !== 'undefined') {{
                SCORM.setProgressMeasure(0.01);
                SCORM.setLocation('1');
                SCORM.commit();
            }}
        }}

        // Обробка оновлення прогресу
        function handleProgressUpdate(data) {{
            // Оновлюємо локальні змінні
            if (data.scrollPercent !== undefined) {{
                scrollProgress = data.scrollPercent;
            }}

            // Передаємо прогрес у SCORM
            var progress = Math.min(scrollProgress / 100, 0.99); // Залишаємо 100% для повного завершення
            if (typeof updateSCORMProgress === 'function') {{
                updateSCORMProgress(progress, currentPage.toString());
            }}

            // Перевіряємо на завершення
            checkCompletion();
        }}

        // Обробка зміни сторінки
        function handlePageChange(data) {{
            if (data.currentPage !== undefined) {{
                currentPage = data.currentPage;

                // Оновлюємо розташування в SCORM
                if (typeof SCORM !== 'undefined') {{
                    SCORM.setLocation(currentPage.toString());
                }}
            }}
        }}

        // Перевірка умов завершення
        function checkCompletion() {{
            if (completed) return;

            // Умови завершення: 90% прокрутки АБО (60+ секунд перегляду І 50%+ прокрутки)
            if (scrollProgress >= 90 || (timeSpent >= 60 && scrollProgress >= 50)) {{
                completed = true;

                // Позначаємо як завершений у SCORM
                if (typeof SCORM !== 'undefined') {{
                    SCORM.setProgressMeasure(1.0); // 100% прогресу
                    SCORM.setCompletionStatus('completed');
                    SCORM.commit();
                }}
            }}
        }}

        // Запуск періодичних оновлень
        function startPeriodicUpdates() {{
            // Оновлення часу і перевірка завершення кожні 3 секунди
            setInterval(function() {{
                if (!completed) {{
                    timeSpent += 3;
                    var sessionDuration = Math.floor((new Date() - sessionStartTime) / 1000);

                    // Оновлюємо час у SCORM кожні 30 секунд
                    if (sessionDuration % 30 === 0 && typeof SCORM !== 'undefined') {{
                        SCORMUtils.updateSessionTime();
                    }}

                    // Перевіряємо умови завершення
                    checkCompletion();
                }}
            }}, 3000);

            // Примусовий commit до LMS кожні 3 хвилини
            setInterval(function() {{
                if (typeof SCORM !== 'undefined' && SCORM.initialized) {{
                    SCORM.commit();
                }}
            }}, 3 * 60 * 1000);
        }}
    </script>
</body>
</html>'''

    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return 'index.html'


def create_scorm_api_js(content_dir, scorm_version):
    """
    Створює JavaScript файл для взаємодії з SCORM API

    Args:
        content_dir (str): Директорія контенту
        scorm_version (str): Версія SCORM ('1.2' або '2004')
    """
    js_content = """// Покращена обгортка для SCORM API
var SCORM = {
    initialized: false,
    apiHandle: null,
    version: null,
    progress: 0,
    debug: false, // Режим відлагодження вимкнено

    // Порожня функція логування (не виводить нічого)
    log: function(message, type) {
        // Логування повністю відключено
    },

    // Ініціалізація SCORM API
    init: function() {
        // Спроба знайти API кілька разів із затримкою
        var maxTries = 15;
        var tries = 0;

        var tryGetAPI = function() {
            this.apiHandle = this.getAPI();
            tries++;

            if (this.apiHandle) {
                this.initializeAPI();
            } else if (tries < maxTries) {
                setTimeout(tryGetAPI.bind(this), 200);
            }
        }.bind(this);

        tryGetAPI();
        return this.initialized;
    },

    // Ініціалізація виявленого API
    initializeAPI: function() {
        if (!this.apiHandle) {
            return false;
        }

        try {
            if (typeof this.apiHandle.Initialize !== 'undefined') {
                this.version = '2004';
                this.initialized = this.apiHandle.Initialize('');
            } else if (typeof this.apiHandle.LMSInitialize !== 'undefined') {
                this.version = '1.2';
                this.initialized = this.apiHandle.LMSInitialize('');
            } else {
                return false;
            }

            if (this.initialized) {
                // Одразу встановлюємо початковий статус
                this.setCompletionStatus('incomplete');

                // Запускаємо періодичне збереження даних
                this.startAutosave();

                return true;
            } else {
                return false;
            }
        } catch (e) {
            return false;
        }
    },

    // Автоматичне збереження даних кожні 3 хвилини
    startAutosave: function() {
        if (!this.initialized) return;

        this.autosaveInterval = setInterval(function() {
            this.commit();
        }.bind(this), 3 * 60 * 1000); // 3 хвилини
    },

    // Отримання останньої помилки
    getLastError: function() {
        if (!this.apiHandle) return 'API не знайдено';

        try {
            if (this.version === '2004') {
                var errorCode = this.apiHandle.GetLastError();
                var errorString = this.apiHandle.GetErrorString(errorCode);
                var errorDescription = this.apiHandle.GetDiagnostic(errorCode);
                return 'Код: ' + errorCode + ', ' + errorString + ' - ' + errorDescription;
            } else if (this.version === '1.2') {
                var errorCode = this.apiHandle.LMSGetLastError();
                var errorString = this.apiHandle.LMSGetErrorString(errorCode);
                var errorDescription = this.apiHandle.LMSGetDiagnostic(errorCode);
                return 'Код: ' + errorCode + ', ' + errorString + ' - ' + errorDescription;
            }
        } catch (e) {
            return 'Помилка при отриманні коду помилки: ' + e.message;
        }

        return 'Невідома помилка';
    },

    // Застосування змін, щоб LMS збереглa їх
    commit: function() {
        if (!this.initialized) return false;

        try {
            var result = false;
            if (this.version === '2004') {
                result = this.apiHandle.Commit('');
            } else if (this.version === '1.2') {
                result = this.apiHandle.LMSCommit('');
            }

            return result;
        } catch (e) {
            return false;
        }
    },

    // Завершення сесії
    terminate: function() {
        if (!this.initialized) return false;

        try {
            // Спочатку зупиняємо автозбереження
            if (this.autosaveInterval) {
                clearInterval(this.autosaveInterval);
            }

            // Перед завершенням зберігаємо дані
            this.commit();

            var result = false;
            if (this.version === '2004') {
                result = this.apiHandle.Terminate('');
            } else if (this.version === '1.2') {
                result = this.apiHandle.LMSFinish('');
            }

            if (result) {
                this.initialized = false;
                return true;
            } else {
                return false;
            }
        } catch (e) {
            return false;
        }
    },

    // Встановлення статусу завершення
    setCompletionStatus: function(status) {
        if (!this.initialized) {
            return false;
        }

        try {
            var result = false;
            if (this.version === '2004') {
                result = this.apiHandle.SetValue('cmi.completion_status', status);
                // Також встановлюємо success_status для SCORM 2004
                if (status === 'completed') {
                    this.apiHandle.SetValue('cmi.success_status', 'passed');
                }
            } else if (this.version === '1.2') {
                var statusMap = {
                    'completed': 'completed',
                    'incomplete': 'incomplete',
                    'not attempted': 'not attempted',
                    'failed': 'failed',
                    'passed': 'passed'
                };
                var mappedStatus = statusMap[status] || 'incomplete';
                result = this.apiHandle.LMSSetValue('cmi.core.lesson_status', mappedStatus);
            }

            if (result) {
                // Одразу зберігаємо встановлене значення
                this.commit();
                return true;
            } else {
                return false;
            }
        } catch (e) {
            return false;
        }
    },

    // Встановлення часу сесії в правильному форматі
    setSessionTime: function(seconds) {
        if (!this.initialized) return false;

        try {
            var result = false;
            if (this.version === '2004') {
                // Формат ISO 8601 (PT1H30M5S)
                var h = Math.floor(seconds / 3600);
                var m = Math.floor((seconds % 3600) / 60);
                var s = Math.floor(seconds % 60);
                var timeValue = 'PT';
                if (h > 0) timeValue += h + 'H';
                if (m > 0) timeValue += m + 'M';
                if (s > 0 || (h === 0 && m === 0)) timeValue += s + 'S';

                result = this.apiHandle.SetValue('cmi.session_time', timeValue);
            } else if (this.version === '1.2') {
                // Формат HH:MM:SS.S
                var h = Math.floor(seconds / 3600);
                var m = Math.floor((seconds % 3600) / 60);
                var s = seconds % 60;
                var timeValue = (h < 10 ? '0' + h : h) + ':' + 
                               (m < 10 ? '0' + m : m) + ':' + 
                               (s < 10 ? '0' + s : s);

                result = this.apiHandle.LMSSetValue('cmi.core.session_time', timeValue);
            }

            return result;
        } catch (e) {
            return false;
        }
    },

    // Отримання поточного статусу
    getCompletionStatus: function() {
        if (!this.initialized) return '';

        try {
            var status = '';
            if (this.version === '2004') {
                status = this.apiHandle.GetValue('cmi.completion_status');
            } else if (this.version === '1.2') {
                status = this.apiHandle.LMSGetValue('cmi.core.lesson_status');
            }

            return status;
        } catch (e) {
            return '';
        }
    },

    // Встановлення прогресу проходження
    setProgressMeasure: function(progress) {
        if (!this.initialized) {
            return false;
        }

        // Переконуємося, що значення прогресу в діапазоні 0-1
        progress = Math.max(0, Math.min(1, progress));
        this.progress = progress;

        try {
            var result = false;

            if (this.version === '2004') {
                result = this.apiHandle.SetValue('cmi.progress_measure', progress.toFixed(2));

                // Також встановлюємо scaled_passing_score якщо його немає
                var passingScore = this.apiHandle.GetValue('cmi.scaled_passing_score');
                if (passingScore === '' || passingScore === 'unknown') {
                    this.apiHandle.SetValue('cmi.scaled_passing_score', '0.7');
                }

                // Встановлюємо score
                this.apiHandle.SetValue('cmi.score.scaled', progress.toFixed(2));
                this.apiHandle.SetValue('cmi.score.raw', Math.round(progress * 100).toString());
                this.apiHandle.SetValue('cmi.score.min', '0');
                this.apiHandle.SetValue('cmi.score.max', '100');
            } else if (this.version === '1.2') {
                // Встановлюємо бали
                var score = Math.round(progress * 100);
                this.apiHandle.LMSSetValue('cmi.core.score.raw', score.toString());
                this.apiHandle.LMSSetValue('cmi.core.score.min', '0');
                this.apiHandle.LMSSetValue('cmi.core.score.max', '100');
                result = true;
            }

            if (result) {
                // Якщо прогрес близький до 100%, встановлюємо статус completed
                if (progress >= 0.9) {
                    this.setCompletionStatus('completed');
                }

                return true;
            } else {
                return false;
            }
        } catch (e) {
            return false;
        }
    },

    // Встановлення розташування (номер сторінки для PDF)
    setLocation: function(location) {
        if (!this.initialized) return false;

        try {
            var result = false;
            if (this.version === '2004') {
                result = this.apiHandle.SetValue('cmi.location', location);
            } else if (this.version === '1.2') {
                result = this.apiHandle.LMSSetValue('cmi.core.lesson_location', location);
            }

            return result;
        } catch (e) {
            return false;
        }
    },

    // Отримання поточного прогресу
    getProgressMeasure: function() {
        return this.progress;
    },

    // Пошук API в ієрархії фреймів
    getAPI: function() {
        var win = window;
        var foundAPI = null;
        var findAPITries = 0;
        var findAPIMaxTries = 15;

        // Функція пошуку API в конкретному вікні
        var lookForAPI = function(win) {
            // Спочатку перевіряємо наявність SCORM 2004 API
            if (win.API_1484_11) {
                return win.API_1484_11;
            }

            // Потім перевіряємо наявність SCORM 1.2 API
            if (win.API) {
                return win.API;
            }

            return null;
        }.bind(this);

        // Спочатку перевіряємо поточне вікно
        foundAPI = lookForAPI(win);
        if (foundAPI) return foundAPI;

        // Пошук API в ієрархії батьківських вікон
        while (win.parent != null && win.parent != win && findAPITries < findAPIMaxTries) {
            findAPITries++;
            win = win.parent;

            foundAPI = lookForAPI(win);
            if (foundAPI) return foundAPI;
        }

        // Пошук API у відкривачі вікна (якщо є)
        if (window.opener != null && typeof window.opener != 'undefined') {
            foundAPI = lookForAPI(window.opener);
            if (foundAPI) return foundAPI;
        }

        return null;
    }
};

// Деякі додаткові утиліти
var SCORMUtils = {
    // Відстеження часу
    startTime: new Date(),

    // Обчислення тривалості сесії в секундах
    getSessionDuration: function() {
        var currentTime = new Date();
        var sessionDuration = Math.floor((currentTime - this.startTime) / 1000);
        return sessionDuration;
    },

    // Оновлення часу сесії в SCORM
    updateSessionTime: function() {
        if (SCORM.initialized) {
            var duration = this.getSessionDuration();
            SCORM.setSessionTime(duration);
        }
    }
};

// Глобальні функції для виклику з HTML
function initializeSCORM() {
    // Встановлюємо обробники подій
    window.addEventListener('beforeunload', function() {
        terminateSCORM();
    });

    // Ініціалізація і початковий статус
    if (SCORM.init()) {
        SCORM.setCompletionStatus('incomplete');

        // Починаємо відстежувати час
        SCORMUtils.startTime = new Date();

        // Періодично оновлюємо час сесії
        setInterval(function() {
            SCORMUtils.updateSessionTime();
        }, 60000); // Кожну хвилину
    } else {
        // Спробуємо ще раз через секунду
        setTimeout(initializeSCORM, 1000);
    }
}

function terminateSCORM() {
    // Останнє оновлення часу перед завершенням
    SCORMUtils.updateSessionTime();

    // Завершення сесії
    if (SCORM.initialized) {
        SCORM.terminate();
    }
}

// Функція для оновлення прогресу
function updateSCORMProgress(progress, location) {
    if (!SCORM.initialized) {
        return;
    }

    // Встановлення прогресу
    SCORM.setProgressMeasure(progress);

    // Якщо передано розташування
    if (location !== undefined) {
        SCORM.setLocation(location);
    }

    // Зберігаємо зміни в LMS
    SCORM.commit();
}

// Пуста функція для перевірки стану SCORM
function checkSCORMStatus() {
    return {
        initialized: SCORM.initialized,
        version: SCORM.version,
        progress: SCORM.progress,
        completionStatus: SCORM.getCompletionStatus()
    };
}
"""

    js_path = os.path.join(content_dir, 'scorm_api.js')
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)


def create_scorm_manifest(content_dir, title, resources, index_file, course_id, scorm_version):
    """
    Створює маніфест SCORM

    Args:
        content_dir (str): Директорія контенту
        title (str): Назва курсу
        resources (dict): Словник з інформацією про ресурси
        index_file (str): Назва індексного HTML-файлу
        course_id (str): Ідентифікатор курсу
        scorm_version (str): Версія SCORM ('1.2' або '2004')
    """
    manifest_path = os.path.join(content_dir, 'imsmanifest.xml')
    print(f"Створення маніфесту SCORM у {manifest_path}")
    print(f"Отримані ресурси: {resources}")

    # Перевірка типу resources
    if not isinstance(resources, dict):
        print(f"УВАГА: resources не є словником: {type(resources)}")
        # Створення порожнього словника ресурсів для запобігання помилкам
        resources = {
            'html': [],
            'css': [],
            'js': [],
            'images': [],
            'fonts': [],
            'other': []
        }

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

    # Додавання SCORM-специфічних атрибутів
    if scorm_version == '1.2':
        item.set('isvisible', 'true')
        prerequisites = ET.SubElement(item, 'adlcp:prerequisites')
        prerequisites.text = ''
        prerequisites.set('type', 'aicc_script')
        maxtimeallowed = ET.SubElement(item, 'adlcp:maxtimeallowed')
        maxtimeallowed.text = ''
        timelimitaction = ET.SubElement(item, 'adlcp:timelimitaction')
        timelimitaction.text = ''
        datafromlms = ET.SubElement(item, 'adlcp:datafromlms')
        datafromlms.text = ''
        masteryscore = ET.SubElement(item, 'adlcp:masteryscore')
        masteryscore.text = ''
    else:  # SCORM 2004
        # Додатковий функціонал для SCORM 2004
        pass

    # Ресурси
    resources_elem = ET.SubElement(manifest, 'resources')

    # Створення основного ресурсу
    resource = ET.SubElement(resources_elem, 'resource')
    resource.set('identifier', 'resource_1')
    resource.set('type', 'webcontent')
    resource.set('href', index_file)

    if scorm_version == '1.2':
        resource.set('adlcp:scormtype', 'sco')
    else:
        resource.set('adlcp:scormType', 'sco')

    # Додавання файлів
    file_list = [index_file, 'scorm_api.js']

    # Додаємо шляхи до ресурсів
    print("Обробка ресурсів для включення в маніфест:")
    for res_type in ['html', 'css', 'js', 'images', 'fonts', 'other']:
        if res_type in resources and isinstance(resources[res_type], list):
            print(f"  Тип {res_type}: {resources[res_type]}")
            for res_file in resources[res_type]:
                file_path = f"resources/{res_file}"
                print(f"    Додавання ресурсу: {file_path}")
                if file_path not in file_list:
                    file_list.append(file_path)
        else:
            print(f"  Пропуск типу {res_type}: відсутній у словнику або не є списком")

    # Рекурсивно додаємо всі файли з директорії ресурсів
    for root, dirs, files in os.walk(os.path.join(content_dir, 'resources')):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), content_dir)
            if rel_path not in file_list:
                file_list.append(rel_path)
                print(f"    Додано ресурс (через сканування директорії): {rel_path}")

    # Додаємо всі файли в ресурс
    print(f"Всього файлів для включення в ресурс: {len(file_list)}")
    for file_path in file_list:
        file_elem = ET.SubElement(resource, 'file')
        file_elem.set('href', file_path)
        print(f"  Додано файл: {file_path}")

    # Форматування XML для кращої читабельності
    rough_string = ET.tostring(manifest, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(reparsed.toprettyxml(indent="  "))

    print("Маніфест SCORM успішно створено")


def convert_pdf_to_scorm(pdf_path, output_path=None, title=None, scorm_version='2004', extract_images=True,
                         debug=False):
    """
    Конвертує PDF файл у SCORM-пакет

    Args:
        pdf_path (str): Шлях до PDF файлу
        output_path (str): Шлях для збереження SCORM-пакету (.zip)
        title (str): Назва курсу (за замовчуванням - назва PDF-файлу)
        scorm_version (str): Версія SCORM ('1.2' або '2004')
        extract_images (bool): Чи видобувати зображення з PDF
        debug (bool): Режим налагодження - зберігає тимчасові файли

    Returns:
        bool: True у разі успіху, False - у разі помилки
    """
    try:
        # Перевірка існування PDF-файлу
        if not os.path.exists(pdf_path):
            print(f"Помилка: Файл '{pdf_path}' не знайдено")
            return False

        # Визначення вихідного файлу, якщо не вказано
        if not output_path:
            output_dir = os.path.dirname(pdf_path) or '.'
            output_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_path = os.path.join(output_dir, f"{output_name}_scorm.zip")

        # Визначення назви курсу, якщо не вказано
        if not title:
            # Використовуємо назву PDF файлу
            title = os.path.splitext(os.path.basename(pdf_path))[0]

            # Спроба отримати заголовок з метаданих PDF
            try:
                doc = fitz.open(pdf_path)
                metadata = doc.metadata
                if metadata and 'title' in metadata and metadata['title']:
                    title = metadata['title']
                doc.close()
            except:
                pass

        # Створення тимчасової директорії для роботи
        temp_dir = tempfile.mkdtemp()
        content_dir = os.path.join(temp_dir, 'content')
        resources_dir = os.path.join(content_dir, 'resources')

        # Створення структури директорій
        os.makedirs(content_dir, exist_ok=True)
        os.makedirs(resources_dir, exist_ok=True)

        # Генерація ідентифікатора курсу
        course_id = str(uuid4())

        # Конвертація PDF в HTML
        print(f"Конвертація PDF в HTML: {pdf_path}")
        html_path, pdf_meta = convert_pdf_to_html(pdf_path, resources_dir, extract_images)

        if not html_path:
            print("Помилка при конвертації PDF в HTML")
            return False

        # Обробка HTML-файлу та пов'язаних ресурсів
        print("Обробка HTML-файлу та копіювання ресурсів...")
        resource_data = process_html_file(html_path, content_dir, resources_dir, True)

        # Переконуємося, що ми отримали валідний словник ресурсів
        if not resource_data:
            print("Отримано порожній список ресурсів, створюємо базовий словник ресурсів")
            resource_data = {
                'html': [os.path.basename(html_path)],
                'css': [],
                'js': [],
                'images': [],
                'fonts': [],
                'other': []
            }

            # Додаємо всі знайдені зображення
            if os.path.exists(os.path.join(resources_dir, 'images')):
                for img_dir, _, files in os.walk(os.path.join(resources_dir, 'images')):
                    for file in files:
                        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                            img_rel_path = os.path.join('images', file)
                            resource_data['images'].append(img_rel_path)
                            print(f"  Додано зображення до ресурсів вручну: {img_rel_path}")

        # Перевірка структури даних resources
        print("Отримані ресурси:")
        for key, value in resource_data.items():
            print(f"{key}: {value}")

        # Перевірка, чи є html ресурси
        if not resource_data.get('html'):
            print("Попередження: Не знайдено HTML ресурсів, додаємо HTML-файл до списку вручну")
            resource_data['html'] = [os.path.basename(html_path)]

            # Перевіряємо наявність файлу і створюємо простий HTML, якщо його немає
            if not os.path.exists(os.path.join(resources_dir, os.path.basename(html_path))):
                print("HTML-файл не знайдено, створюємо запасний HTML")
                pdf_info = {'title': title, 'pages': 0}

                # Підраховуємо кількість сторінок по зображеннях
                if os.path.exists(os.path.join(resources_dir, 'images')):
                    page_count = 0
                    for file in os.listdir(os.path.join(resources_dir, 'images')):
                        if file.lower().startswith('page') and file.lower().endswith('.png'):
                            try:
                                page_num = int(file.lower().replace('page', '').split('.')[0])
                                page_count = max(page_count, page_num)
                            except:
                                pass
                    pdf_info['pages'] = page_count

                create_fallback_html(os.path.join(resources_dir, os.path.basename(html_path)), resource_data, pdf_info)

        # Створення обгортки для SCORM
        print("Створення SCORM-обгортки...")
        index_path = create_scorm_wrapper(content_dir, title, os.path.basename(html_path), resource_data['html'])

        # Створення JavaScript для SCORM API
        print("Створення JavaScript для SCORM API...")
        create_scorm_api_js(content_dir, scorm_version)

        # Створення маніфесту SCORM
        print("Створення маніфесту SCORM...")
        create_scorm_manifest(content_dir, title, resource_data, index_path, course_id, scorm_version)

        # Створення ZIP-архіву
        print("Створення ZIP-архіву...")
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(content_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(
                        file_path,
                        os.path.relpath(file_path, content_dir)
                    )

        # Очищення тимчасових файлів (якщо не режим налагодження)
        if not debug:
            shutil.rmtree(temp_dir)
            print("Тимчасові файли видалено")
        else:
            print(f"Режим налагодження: тимчасові файли збережено в {temp_dir}")

        print(f"SCORM-пакет успішно створено: {output_path}")
        return True

    except Exception as e:
        print(f"Помилка при конвертації PDF в SCORM: {e}")
        import traceback
        traceback.print_exc()
        # Спроба очистити тимчасові файли у випадку помилки
        try:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
        return False


def main():
    """
    Головна функція для конвертування PDF файлів у SCORM-пакети
    """
    parser = argparse.ArgumentParser(description='Конвертер PDF у SCORM-пакети')
    parser.add_argument('input_file', nargs='?', help='Шлях до вхідного PDF файлу')
    parser.add_argument('--output', '-o', help='Шлях до вихідного SCORM-пакету (.zip)')
    parser.add_argument('--title', '-t', help='Назва курсу (за замовчуванням - назва PDF-файлу)')
    parser.add_argument('--scorm-version', '-v', choices=['1.2', '2004'], default='2004',
                        help='Версія SCORM (1.2 або 2004)')
    parser.add_argument('--no-images', '-n', action='store_true',
                        help='Не видобувати зображення з PDF')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Режим налагодження - зберігає тимчасові файли')

    args = parser.parse_args()

    # Якщо файл не вказано, показуємо список файлів у поточній директорії
    if not args.input_file:
        print("=== PDF to SCORM КОНВЕРТЕР ===")
        print("Цей скрипт конвертує PDF файли в SCORM-пакети\n")

        # Збираємо список файлів у поточній директорії
        pdf_files = [f for f in os.listdir('') if os.path.isfile(f) and
                     f.lower().endswith('.pdf')]

        if pdf_files:
            print("Знайдено PDF файли в поточній директорії:")
            for i, file in enumerate(pdf_files, 1):
                print(f"{i}. {file}")
            print("\nВиберіть номер файлу або введіть повний шлях до файлу:")

            file_input = input("> ").strip()
            try:
                file_index = int(file_input) - 1
                if 0 <= file_index < len(pdf_files):
                    args.input_file = pdf_files[file_index]
                else:
                    args.input_file = file_input
            except ValueError:
                args.input_file = file_input
        else:
            args.input_file = input("Введіть шлях до PDF файлу: ").strip()

    # Перевірка наявності файлу
    if not os.path.exists(args.input_file):
        print(f"Помилка: Файл '{args.input_file}' не знайдено")
        sys.exit(1)

    # Визначення типу файлу
    is_pdf = args.input_file.lower().endswith('.pdf')

    if not is_pdf:
        print("Помилка: Непідтримуваний тип файлу")
        print("Підтримуваний формат: PDF")
        sys.exit(1)

    # Визначення вихідного SCORM-пакету
    if not args.output:
        output_path = os.path.splitext(args.input_file)[0] + "_scorm.zip"
        confirm = input(f"Конвертувати PDF-файл в SCORM-пакет '{output_path}'? (y/n) [y]: ").strip().lower()
        if confirm != 'n':
            args.output = output_path
        else:
            args.output = input("Введіть шлях для збереження SCORM-пакету: ").strip()

    # Запитуємо назву курсу, якщо не вказано
    if not args.title:
        try:
            doc = fitz.open(args.input_file)
            metadata = doc.metadata
            default_title = metadata.get('title', os.path.splitext(os.path.basename(args.input_file))[0])
            doc.close()
        except:
            default_title = os.path.splitext(os.path.basename(args.input_file))[0]

        args.title = input(f"Назва курсу [{default_title}]: ").strip() or default_title

    print(f"\nКонвертація PDF-файлу {args.input_file} в SCORM-пакет...")
    result = convert_pdf_to_scorm(
        args.input_file,
        args.output,
        args.title,
        args.scorm_version,
        not args.no_images,
        args.debug
    )

    if result:
        print(f"PDF-файл успішно конвертовано в SCORM-пакет: {args.output}")
    else:
        print("Помилка при конвертації PDF в SCORM")
        sys.exit(1)


if __name__ == "__main__":
    main()