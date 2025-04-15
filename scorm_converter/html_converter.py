import argparse
# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile
import shutil
import zipfile
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from datetime import datetime
from uuid import uuid4
import re
from pathlib import Path
from bs4 import BeautifulSoup
import base64
import sys


def convert_html_to_scorm(html_path, output_path=None, title=None, scorm_version='2004', include_resources=True):
    """
    Конвертує HTML-файл та пов'язані ресурси у SCORM-пакет

    Args:
        html_path (str): Шлях до HTML-файлу
        output_path (str): Шлях для збереження SCORM-пакету (.zip)
        title (str): Назва курсу (за замовчуванням - назва HTML-файлу)
        scorm_version (str): Версія SCORM ('1.2' або '2004')
        include_resources (bool): Чи включати пов'язані ресурси (CSS, зображення тощо)

    Returns:
        bool: True у разі успіху, False - у разі помилки
    """
    try:
        # Перевірка існування HTML-файлу
        if not os.path.exists(html_path):
            print(f"Помилка: Файл '{html_path}' не знайдено")
            return False

        # Визначення вихідного файлу, якщо не вказано
        if not output_path:
            output_dir = os.path.dirname(html_path) or '.'
            output_name = os.path.splitext(os.path.basename(html_path))[0]
            output_path = os.path.join(output_dir, f"{output_name}_scorm.zip")

        # Визначення назви курсу, якщо не вказано
        if not title:
            title = os.path.splitext(os.path.basename(html_path))[0]

            # Спроба отримати заголовок з HTML-файлу
            try:
                with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                    html_content = f.read()
                soup = BeautifulSoup(html_content, 'html.parser')
                title_tag = soup.find('title')
                if title_tag and title_tag.string:
                    title = title_tag.string.strip()
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

        # Копіювання HTML-файлу та пов'язаних ресурсів
        print("Обробка HTML-файлу та копіювання ресурсів...")
        resource_data = process_html_file(html_path, content_dir, resources_dir, include_resources)

        # Перевірка структури даних resources
        print("Отримані ресурси:")
        for key, value in resource_data.items():
            print(f"{key}: {value}")

        # Перевірка, чи є html ресурси
        if not resource_data['html']:
            print("Помилка: Не знайдено HTML ресурсів після обробки файлу")
            return False

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

        # Очищення тимчасових файлів
        shutil.rmtree(temp_dir)

        print(f"SCORM-пакет успішно створено: {output_path}")
        return True

    except Exception as e:
        print(f"Помилка при конвертації HTML в SCORM: {e}")
        import traceback
        traceback.print_exc()
        # Спроба очистити тимчасові файли у випадку помилки
        try:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
        return False


def process_html_file(html_path, content_dir, resources_dir, include_resources=True):
    """
    Обробляє HTML-файл та копіює пов'язані ресурси, з можливістю додавання підписування AWS для зовнішніх ресурсів
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

    # Проблемні домени, які можуть потребувати AWS підписування
    problematic_domains = [
        'cloudflare', 'cloudflarestorage', 'r2.',
        'amazonaws', 's3.', 'cloudfront',
        'storage.googleapis'
    ]

    try:
        # Читаємо HTML-вміст
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        print(f"Успішно прочитано HTML-файл довжиною {len(html_content)} символів")

        # Перевірка на наявність проблемних зовнішніх посилань перед обробкою
        for domain in problematic_domains:
            if domain in html_content:
                print(f"УВАГА! Знайдено потенційно проблемне посилання на {domain} у HTML")

        # Парсимо HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        print("HTML успішно розібрано за допомогою BeautifulSoup")


        # Інтегруємо всі стилі в head
        all_styles = []
        for style in soup.find_all('style'):
            all_styles.append(style.string or '')
            style.decompose()

        # Створюємо новий style тег
        if all_styles:
            head = soup.find('head')
            if head:
                style_tag = soup.new_tag('style')
                style_tag.string = '\n'.join(all_styles)
                head.append(style_tag)
                print("Всі стилі об'єднано в один тег <style> у <head>")

        # Інтегруємо всі скрипти в кінець body
        all_scripts = []
        for script in soup.find_all('script'):
            if not script.has_attr('src'):  # збираємо лише інлайн скрипти
                all_scripts.append(script.string or '')
            script.decompose()

        # Створюємо новий script тег
        if all_scripts:
            body = soup.find('body')
            if body:
                script_tag = soup.new_tag('script')
                script_tag.string = '\n'.join(all_scripts)
                body.append(script_tag)
                print("Всі скрипти об'єднано в один тег <script> в кінці <body>")

        # Видаляємо коментарі
        from bs4.element import Comment
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
            print("Видалено HTML-коментар")

        # Додаємо meta тег для запобігання зовнішніх запитів
        head = soup.find('head')
        if head:
            meta_csp = soup.new_tag('meta')
            meta_csp['http-equiv'] = 'Content-Security-Policy'
            meta_csp[
                'content'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
            head.insert(0, meta_csp)
            print("Додано Content-Security-Policy для захисту від зовнішніх запитів")

        # В функції process_html_file перед збереженням HTML
        # Додаємо AWS Signature скрипт, якщо в HTML є посилання на cloudflare/s3
        if any(domain in str(soup) for domain in problematic_domains):
            access_key = "YOUR_ACCESS_KEY"
            secret_key = "YOUR_SECRET_KEY"
            region = "auto"  # Для Cloudflare R2 зазвичай використовується 'auto'
            service = "s3"  # Для S3-сумісних сервісів використовується 's3'

            # Додаємо скрипт для підписування
            soup = add_aws_signature_script(soup, access_key, secret_key, region, service)
            print("Додано скрипт для автоматичного підписування запитів до Cloudflare R2/S3")

        # Зберігаємо оновлений HTML-вміст
        print(f"Збереження оновленого HTML в {html_dest}")
        with open(html_dest, 'w', encoding='utf-8') as f:
            f.write(str(soup))

        # Додаємо HTML до списку ресурсів
        resources['html'].append(html_filename)
        print(f"Додано HTML-файл {html_filename} до списку ресурсів")

    except Exception as e:
        print(f"Помилка при обробці HTML-файлу: {e}")
        import traceback
        traceback.print_exc()

        # Створюємо замість проблемного HTML простий чистий HTML без зовнішніх ресурсів
        clean_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Error </title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #2980b9; margin-top: 30px; }}
        p, li {{ font-size: 16px; line-height: 1.6; }}
        .info-box {{ background-color: #e8f4fc; border-left: 4px solid #3498db; padding: 15px; margin: 20px 0; }}
        .warning-box {{ background-color: #fff5e6; border-left: 4px solid #e67e22; padding: 15px; margin: 20px 0; }}
    </style>
</head>
<body>
</body>
</html>"""

        with open(html_dest, 'w', encoding='utf-8') as f:
            f.write(clean_html)

        resources['html'].append(html_filename)
        print(f"Створено простий HTML-файл замість проблемного")

    print("Завершено обробку HTML-файлу")
    return resources


def create_scorm_wrapper(content_dir, title, html_filename, html_files):
    """
    Створює безпечну HTML-обгортку для SCORM, яка блокує всі зовнішні запити
    і забезпечує правильне відстеження статистики
    """
    index_path = os.path.join(content_dir, 'index.html')

    # Очищення title від потенційно небезпечних HTML-тегів
    title = BeautifulSoup(title, "html.parser").get_text()

    # Створення HTML-обгортки для SCORM з максимальним захистом від зовнішніх запитів
    # та покращеним відстеженням статистики
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
        #header {{
            background-color: #2c3e50;
            color: white;
            padding: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }}
        #content-container {{
            width: 100%;
            height: calc(100% - 60px);
            overflow: auto;
        }}
        #content-frame {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        #statistics-info {{
            position: fixed;
            bottom: 0;
            left: 0;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 5px 10px;
            font-size: 12px;
            z-index: 1000;
            display: none;
        }}
    </style>
</head>
<body onload="initializeSCORM();" onunload="terminateSCORM();">
    <div id="header">
        <h1>{title}</h1>
    </div>
    <div id="content-container">
        <iframe id="content-frame" src="resources/{html_filename}" sandbox="allow-same-origin allow-scripts allow-forms" onload="contentLoaded();"></iframe>
    </div>
    <div id="statistics-info"></div>
    <script>
        // Розширений скрипт для відстеження прогресу
        var timeSpent = 0;
        var completed = false;
        var lastActivity = new Date();
        var pageViews = 1;
        var totalPages = 1;
        var statsInterval;
        var debugMode = false; // Встановіть true для відображення налагоджувальної інформації

        // Ініціалізація SCORM та налаштування відстеження статистики
        function initializeSCORM() {{
            // Ініціалізація SCORM API
            if (typeof SCORM !== 'undefined') {{
                var success = SCORM.init();

                if (success) {{
                    // Отримуємо поточний статус для відновлення сесії
                    var currentStatus = SCORM.getCompletionStatus();
                    console.log("SCORM initialized. Current status: " + currentStatus);

                    // Відновлюємо progress з LMS, якщо він є
                    var storedProgress = SCORM.getProgressMeasure();
                    if (storedProgress !== "") {{
                        timeSpent = Math.floor(storedProgress * 120); // Обернене перетворення
                    }}

                    // Встановлюємо статус "incomplete" при першому запуску
                    if (currentStatus === "not attempted" || currentStatus === "") {{
                        SCORM.setCompletionStatus("incomplete");
                        // Фіксуємо зміни у LMS
                        SCORM.commit();
                    }} else if (currentStatus === "completed") {{
                        completed = true;
                    }}

                    // Створюємо об'єктив курсу для статистики
                    var courseObjective = SCORMTracker.startQuiz("course_main", "{title}");

                    // Запускаємо таймер для оновлення статистики
                    startStatisticsTimer();
                }} else {{
                    console.error("Failed to initialize SCORM API");
                }}
            }} else {{
                console.error("SCORM API not found");
            }}

            // Відстеження активності користувача
            document.addEventListener('click', updateUserActivity);
            document.addEventListener('keydown', updateUserActivity);
            document.addEventListener('mousemove', updateUserActivity);
            document.addEventListener('scroll', updateUserActivity);

            // Перехоплення повідомлень від iframe
            window.addEventListener('message', handleFrameMessages);

            if (debugMode) {{
                // Показуємо налагоджувальну інформацію
                var statsInfo = document.getElementById('statistics-info');
                statsInfo.style.display = 'block';
            }}
        }}

        // Функція виклику при завантаженні контенту iframe
        function contentLoaded() {{
            // Запис взаємодії "page_view"
            if (typeof SCORMTracker !== 'undefined') {{
                var interactionId = SCORMTracker.startQuestion("page_view_" + pageViews, "true-false", "Перегляд сторінки");
                SCORMTracker.recordAnswer(interactionId, "true", "true", true);
                pageViews++;
            }}

            // Перевірка на завантаження сторінки для запуску оновлення статистики
            checkContentAndUpdateStats();

            // Спроба встановити зв'язок з iframe
            var iframe = document.getElementById('content-frame');
            try {{
                iframe.contentWindow.postMessage({{ type: 'scorm-parent-ready' }}, '*');
            }} catch (e) {{
                console.log("Could not send message to iframe: ", e);
            }}
        }}

        // Функція для перевірки контенту і оновлення статистики
        function checkContentAndUpdateStats() {{
            var iframe = document.getElementById('content-frame');

            try {{
                // Спроба отримати доступ до контенту iframe для аналізу структури
                var iframeDoc = iframe.contentWindow.document;

                // Підрахунок сторінок/секцій, якщо можливо
                var sections = iframeDoc.querySelectorAll('section, .section, .page, .slide, article, .content-block');
                if (sections.length > 0) {{
                    totalPages = Math.max(totalPages, sections.length);
                    updateProgressBasedOnTotalPages();
                }}

                // Інтеграція зі скриптами відстеження в контенті
                var contentLoaded = (iframeDoc.readyState === 'complete');
                if (contentLoaded && typeof iframe.contentWindow.updateParentProgress === 'function') {{
                    // Контент має власну функцію для оновлення прогресу
                    console.log("Content has custom progress tracking");
                }}
            }} catch (e) {{
                // Помилка доступу до iframe - це нормально для cross-origin обмежень
                console.log("Could not access iframe content directly: ", e);
            }}
        }}

        // Обробка повідомлень від iframe
        function handleFrameMessages(event) {{
            if (event.data && typeof event.data === 'object') {{
                if (event.data.type === 'scorm-progress-update') {{
                    // Оновлення прогресу від контенту
                    updateProgress(event.data.progress);
                }} else if (event.data.type === 'scorm-interaction') {{
                    // Запис взаємодії від контенту
                    if (typeof SCORMTracker !== 'undefined') {{
                        var interaction = event.data.interaction;
                        var interactionId = SCORMTracker.startQuestion(
                            interaction.id,
                            interaction.type,
                            interaction.description
                        );
                        SCORMTracker.recordAnswer(
                            interactionId,
                            interaction.response,
                            interaction.correctResponse,
                            interaction.result === 'correct'
                        );
                    }}
                }} else if (event.data.type === 'scorm-complete') {{
                    // Позначення курсу як завершеного від контенту
                    markAsCompleted();
                }}
            }}
        }}

        // Запуск таймера для оновлення статистики
        function startStatisticsTimer() {{
            // Основний таймер для оновлення статистики кожні 15 секунд
            statsInterval = setInterval(function() {{
                if (!completed) {{
                    timeSpent += 15;

                    // Перевірка активності користувача - якщо немає активності більше 5 хвилин,
                    // не зараховуємо цей час
                    var inactive = (new Date() - lastActivity) / 1000 > 300;
                    if (!inactive) {{
                        // Оновлення відображення статистики для відлагодження
                        updateDebugStatisticsDisplay();

                        // Автоматичне завершення після певного часу перегляду (опціонально)
                        if (timeSpent >= 300 && !completed) {{ // 5 хвилин (300 секунд)
                            markAsCompleted();
                        }} else {{
                            // Оновлення прогресу в SCORM
                            updateProgressBasedOnTime();
                        }}
                    }}
                }}
            }}, 15000); // Кожні 15 секунд

            // Оновлення статистики в LMS кожні 60 секунд
            setInterval(function() {{
                if (typeof SCORM !== 'undefined' && SCORM.initialized) {{
                    // Збереження сесії в LMS
                    SCORM.commit();
                    // Оновлення часу сесії
                    SCORMTracker.updateSessionTime();
                }}
            }}, 60000); // Кожну хвилину
        }}

        // Оновлення прогресу на основі часу
        function updateProgressBasedOnTime() {{
            if (typeof SCORM !== 'undefined' && SCORM.initialized) {{
                // Максимальний час для проходження (10 хвилин = 600 секунд)
                var maxTime = 600;
                var progress = Math.min(timeSpent / maxTime, 0.95); // Макс 95% від часу

                // Оновлення значення прогресу
                SCORM.setProgressMeasure(progress);

                // Оновлення відображення для відлагодження
                updateDebugStatisticsDisplay();
            }}
        }}

        // Оновлення прогресу на основі переглянутих сторінок
        function updateProgressBasedOnTotalPages() {{
            if (typeof SCORM !== 'undefined' && SCORM.initialized) {{
                // Розрахунок прогресу на основі переглянутих сторінок
                var pagesProgress = Math.min(pageViews / totalPages, 1);
                var timeProgress = Math.min(timeSpent / 600, 1); // 10 хвилин максимум

                // Комбінуємо обидва показники прогресу з перевагою сторінок
                var combinedProgress = (pagesProgress * 0.7) + (timeProgress * 0.3);

                // Оновлення значення прогресу
                SCORM.setProgressMeasure(combinedProgress);

                // Оновлення відображення для відлагодження
                updateDebugStatisticsDisplay();
            }}
        }}

        // Позначення курсу як завершеного
        function markAsCompleted() {{
            if (!completed && typeof SCORM !== 'undefined' && SCORM.initialized) {{
                completed = true;

                // Встановлення максимального прогресу
                SCORM.setProgressMeasure(1.0);

                // Встановлення статусу "completed"
                SCORM.setCompletionStatus("completed");

                // Фіксація змін у LMS
                SCORM.commit();

                console.log("Course marked as completed");

                // Оновлення відображення для відлагодження
                updateDebugStatisticsDisplay();
            }}
        }}

        // Функція оновлення інформації про останню активність користувача
        function updateUserActivity() {{
            lastActivity = new Date();
        }}

        // Оновлення відображення статистики для відлагодження
        function updateDebugStatisticsDisplay() {{
            if (debugMode) {{
                var statsInfo = document.getElementById('statistics-info');
                var status = completed ? "Завершено" : "В процесі";
                var progress = typeof SCORM !== 'undefined' ? SCORM.getProgressMeasure() : "N/A";
                progress = Math.round(progress * 100);

                statsInfo.innerHTML = `Статус: ${{status}} | Прогрес: ${{progress}}% | Час: ${{Math.floor(timeSpent/60)}}:${{(timeSpent%60).toString().padStart(2,'0')}} | Сторінки: ${{pageViews-1}}/${{totalPages}}`;
            }}
        }}

        // Функція завершення роботи зі SCORM при вивантаженні сторінки
        function terminateSCORM() {{
            // Оновлення часу сесії перед завершенням
            if (typeof SCORMTracker !== 'undefined') {{
                SCORMTracker.updateSessionTime();
            }}

            // Завершення сесії SCORM
            if (typeof SCORM !== 'undefined' && SCORM.initialized) {{
                SCORM.terminate();
            }}

            // Очищення інтервалів
            if (statsInterval) {{
                clearInterval(statsInterval);
            }}
        }}

        // Блокуємо помилки мережевих запитів
        window.addEventListener('error', function(e) {{
            if (e.target && (e.target.tagName === 'IMG' || e.target.tagName === 'SCRIPT' || e.target.tagName === 'LINK')) {{
                console.log('Заблоковано помилку ресурсу:', e.target.src || e.target.href);
                return true; // Відміняємо стандартну обробку помилки
            }}
        }}, true);

        // Перехоплюємо fetch і XMLHttpRequest
        (function() {{
            // Перевизначаємо fetch
            var originalFetch = window.fetch;
            window.fetch = function() {{
                console.log('Спроба використати fetch заблокована');
                return Promise.reject(new Error('fetch заблоковано'));
            }};

            // Перевизначаємо XMLHttpRequest
            var originalXHR = window.XMLHttpRequest;
            window.XMLHttpRequest = function() {{
                console.log('Спроба використати XMLHttpRequest заблокована');
                var xhr = new originalXHR();
                xhr.open = function() {{
                    console.log('XHR.open заблоковано');
                    throw new Error('XMLHttpRequest заблоковано');
                }};
                return xhr;
            }};
        }})();
    </script>
</body>
</html>'''

    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return 'index.html'


def create_scorm_api_js(content_dir, scorm_version):
    """
    Створює JavaScript файл для взаємодії з SCORM API з розширеною підтримкою статистики

    Args:
        content_dir (str): Директорія контенту
        scorm_version (str): Версія SCORM ('1.2' або '2004')
    """
    js_content = """// Покращена обгортка для SCORM API з підтримкою статистики
var SCORM = {
    initialized: false,
    apiHandle: null,
    version: null,
    progress: 0,
    currentInteraction: 0, // Лічильник для унікальних ID взаємодій
    currentObjective: 0,   // Лічильник для унікальних ID цілей
    lastError: "",         // Останнє повідомлення про помилку

    // Ініціалізація SCORM API
    init: function() {
        // Log initialization attempt
        console.log("Attempting to initialize SCORM API...");

        // Get API handle
        this.apiHandle = this.getAPI();

        if (this.apiHandle) {
            console.log("SCORM API handle found");
            let initResult = false;

            if (typeof this.apiHandle.Initialize !== 'undefined') {
                this.version = '2004';
                console.log("Initializing SCORM 2004 API");
                initResult = this.apiHandle.Initialize('');

                // Check for errors
                if (initResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("SCORM 2004 initialization failed: " + this.lastError);
                }
            } else if (typeof this.apiHandle.LMSInitialize !== 'undefined') {
                this.version = '1.2';
                console.log("Initializing SCORM 1.2 API");
                initResult = this.apiHandle.LMSInitialize('');

                // Check for errors
                if (initResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("SCORM 1.2 initialization failed: " + this.lastError);
                }
            } else {
                console.error("Unknown SCORM API version");
            }

            this.initialized = initResult;

            if (this.initialized) {
                console.log("SCORM " + this.version + " API initialized successfully");

                // Set initial data
                if (this.version === '2004') {
                    // Initialize required CMI data
                    this.apiHandle.SetValue('cmi.completion_status', 'incomplete');
                    this.apiHandle.SetValue('cmi.exit', '');
                    this.apiHandle.SetValue('cmi.success_status', 'unknown');
                    // Set session time to zero for new session
                    this.apiHandle.SetValue('cmi.session_time', 'PT0H0M0S');
                } else if (this.version === '1.2') {
                    // Initialize required CMI data
                    this.apiHandle.LMSSetValue('cmi.core.lesson_status', 'incomplete');
                    this.apiHandle.LMSSetValue('cmi.core.exit', '');
                    // Set session time to zero for new session
                    this.apiHandle.LMSSetValue('cmi.core.session_time', '0000:00:00.00');
                }

                // Commit the initial data
                this.commit();
            }

            return this.initialized;
        } else {
            console.error("SCORM API handle not found");
            return false;
        }
    },

    // Завершення сесії
    terminate: function() {
        if (!this.initialized) {
            console.warn("Cannot terminate - SCORM not initialized");
            return false;
        }

        console.log("Terminating SCORM session...");
        var result = false;

        // Ensure we update session time before terminating
        if (typeof SCORMTracker !== 'undefined') {
            SCORMTracker.updateSessionTime();
        }

        try {
            if (this.version === '2004') {
                // Set exit to normal before terminating
                this.apiHandle.SetValue('cmi.exit', 'normal');
                this.commit();

                result = this.apiHandle.Terminate('');

                // Check for errors
                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("SCORM 2004 termination failed: " + this.lastError);
                }
            } else if (this.version === '1.2') {
                // Set exit to normal before terminating
                this.apiHandle.LMSSetValue('cmi.core.exit', 'normal');
                this.commit();

                result = this.apiHandle.LMSFinish('');

                // Check for errors
                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("SCORM 1.2 termination failed: " + this.lastError);
                }
            }
        } catch (e) {
            console.error("Exception during SCORM termination: " + e.message);
            result = false;
        }

        this.initialized = false;
        console.log("SCORM session terminated with result: " + result);
        return result;
    },

    // Застосування змін
    commit: function() {
        if (!this.initialized) {
            console.warn("Cannot commit - SCORM not initialized");
            return false;
        }

        console.log("Committing SCORM data...");
        var result = false;

        try {
            if (this.version === '2004') {
                result = this.apiHandle.Commit('');

                // Check for errors
                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("SCORM 2004 commit failed: " + this.lastError);
                }
            } else if (this.version === '1.2') {
                result = this.apiHandle.LMSCommit('');

                // Check for errors
                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("SCORM 1.2 commit failed: " + this.lastError);
                }
            }
        } catch (e) {
            console.error("Exception during SCORM commit: " + e.message);
            result = false;
        }

        console.log("SCORM commit result: " + result);
        return result;
    },

    // Отримання повідомлення про помилку від LMS
    getLMSErrorMessage: function() {
        if (!this.apiHandle) {
            return "No SCORM API handle available";
        }

        var errorCode = 0;
        var errorMessage = "";

        if (this.version === '2004') {
            errorCode = this.apiHandle.GetLastError();
            errorMessage = this.apiHandle.GetErrorString(errorCode);
            // Add diagnostic info if available
            var diagnostic = this.apiHandle.GetDiagnostic(errorCode);
            if (diagnostic && diagnostic !== errorMessage) {
                errorMessage += " - " + diagnostic;
            }
        } else if (this.version === '1.2') {
            errorCode = this.apiHandle.LMSGetLastError();
            errorMessage = this.apiHandle.LMSGetErrorString(errorCode);
            // Add diagnostic info if available
            var diagnostic = this.apiHandle.LMSGetDiagnostic(errorCode);
            if (diagnostic && diagnostic !== errorMessage) {
                errorMessage += " - " + diagnostic;
            }
        }

        return "Error (" + errorCode + "): " + errorMessage;
    },

    // Встановлення статусу завершення
    setCompletionStatus: function(status) {
        if (!this.initialized) {
            console.warn("Cannot set completion status - SCORM not initialized");
            return false;
        }

        console.log("Setting completion status to: " + status);
        var result = false;

        try {
            if (this.version === '2004') {
                // First, validate the status
                var validStatuses = ['completed', 'incomplete', 'not attempted', 'unknown'];
                if (validStatuses.indexOf(status) === -1) {
                    console.error("Invalid completion status for SCORM 2004: " + status);
                    return false;
                }

                result = this.apiHandle.SetValue('cmi.completion_status', status);

                // Also set success_status if appropriate
                if (status === 'completed') {
                    this.apiHandle.SetValue('cmi.success_status', 'passed');
                }

                // Check for errors
                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set completion status: " + this.lastError);
                }
            } else if (this.version === '1.2') {
                // Map SCORM 2004 statuses to SCORM 1.2
                var statusMap = {
                    'completed': 'completed',
                    'incomplete': 'incomplete',
                    'not attempted': 'not attempted',
                    'failed': 'failed',
                    'passed': 'passed',
                    'unknown': 'incomplete' // Default for unknown
                };

                var mappedStatus = statusMap[status] || 'incomplete';
                result = this.apiHandle.LMSSetValue('cmi.core.lesson_status', mappedStatus);

                // Check for errors
                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set lesson status: " + this.lastError);
                }
            }
        } catch (e) {
            console.error("Exception setting completion status: " + e.message);
            result = false;
        }

        return result;
    },

    // Отримання поточного статусу
    getCompletionStatus: function() {
        if (!this.initialized) {
            console.warn("Cannot get completion status - SCORM not initialized");
            return '';
        }

        console.log("Getting current completion status");
        var status = '';

        try {
            if (this.version === '2004') {
                status = this.apiHandle.GetValue('cmi.completion_status');

                // Check for errors
                if (status === '') {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to get completion status: " + this.lastError);
                }
            } else if (this.version === '1.2') {
                status = this.apiHandle.LMSGetValue('cmi.core.lesson_status');

                // Check for errors
                if (status === '') {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to get lesson status: " + this.lastError);
                }
            }
        } catch (e) {
            console.error("Exception getting completion status: " + e.message);
            status = '';
        }

        console.log("Current completion status: " + status);
        return status;
    },

    // Встановлення прогресу проходження
    setProgressMeasure: function(progress) {
        if (!this.initialized) {
            console.warn("Cannot set progress - SCORM not initialized");
            return false;
        }

        // Validate and sanitize progress value
        if (typeof progress !== 'number') {
            try {
                progress = parseFloat(progress);
            } catch (e) {
                console.error("Invalid progress value, must be a number: " + progress);
                return false;
            }
        }

        // Ensure progress is between 0 and 1
        progress = Math.max(0, Math.min(1, progress));
        this.progress = progress;

        console.log("Setting progress measure to: " + progress);
        var result = false;

        try {
            if (this.version === '2004') {
                // SCORM 2004 has direct support for progress_measure
                result = this.apiHandle.SetValue('cmi.progress_measure', progress.toString());

                // Check for errors
                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set progress measure: " + this.lastError);
                }

                // Also update score as a fallback/additional indicator
                this.apiHandle.SetValue('cmi.score.scaled', progress.toString());
                this.apiHandle.SetValue('cmi.score.raw', Math.round(progress * 100).toString());
                this.apiHandle.SetValue('cmi.score.min', '0');
                this.apiHandle.SetValue('cmi.score.max', '100');
            } else if (this.version === '1.2') {
                // SCORM 1.2 doesn't have progress_measure, use score instead
                result = this.apiHandle.LMSSetValue('cmi.core.score.raw', Math.round(progress * 100).toString());

                // Set min and max scores to provide context
                this.apiHandle.LMSSetValue('cmi.core.score.min', '0');
                this.apiHandle.LMSSetValue('cmi.core.score.max', '100');

                // Check for errors
                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set score: " + this.lastError);
                }
            }
        } catch (e) {
            console.error("Exception setting progress measure: " + e.message);
            result = false;
        }

        return result;
    },

    // Отримання поточного прогресу
    getProgressMeasure: function() {
        if (!this.initialized) {
            console.warn("Cannot get progress - SCORM not initialized");
            return 0;
        }

        console.log("Getting current progress measure");
        var progress = 0;

        try {
            if (this.version === '2004') {
                // Try to get progress_measure first
                var progressStr = this.apiHandle.GetValue('cmi.progress_measure');

                if (progressStr !== '' && !isNaN(parseFloat(progressStr))) {
                    progress = parseFloat(progressStr);
                } else {
                    // Fall back to score if progress_measure is not available
                    var scoreStr = this.apiHandle.GetValue('cmi.score.scaled');
                    if (scoreStr !== '' && !isNaN(parseFloat(scoreStr))) {
                        progress = parseFloat(scoreStr);
                    } else {
                        // Try raw score as a last resort
                        var rawScoreStr = this.apiHandle.GetValue('cmi.score.raw');
                        var maxScoreStr = this.apiHandle.GetValue('cmi.score.max');

                        if (rawScoreStr !== '' && maxScoreStr !== '' && 
                            !isNaN(parseFloat(rawScoreStr)) && !isNaN(parseFloat(maxScoreStr)) && 
                            parseFloat(maxScoreStr) > 0) {
                            progress = parseFloat(rawScoreStr) / parseFloat(maxScoreStr);
                        }
                    }
                }
            } else if (this.version === '1.2') {
                // SCORM 1.2 doesn't have progress_measure, use score instead
                var rawScoreStr = this.apiHandle.LMSGetValue('cmi.core.score.raw');
                var maxScoreStr = this.apiHandle.LMSGetValue('cmi.core.score.max');

                if (rawScoreStr !== '' && !isNaN(parseFloat(rawScoreStr))) {
                    if (maxScoreStr !== '' && !isNaN(parseFloat(maxScoreStr)) && parseFloat(maxScoreStr) > 0) {
                        progress = parseFloat(rawScoreStr) / parseFloat(maxScoreStr);
                    } else {
                        // Assume 100 as max score if not specified
                        progress = parseFloat(rawScoreStr) / 100;
                    }
                }
            }
        } catch (e) {
            console.error("Exception getting progress measure: " + e.message);
            progress = 0;
        }

        // Ensure progress is between 0 and 1
        progress = Math.max(0, Math.min(1, progress));
        this.progress = progress;

        console.log("Current progress measure: " + progress);
        return progress;
    },

    // ==================== СТАТИСТИКА: ВЗАЄМОДІЇ (INTERACTIONS) ====================

    // Додати нову взаємодію
    createInteraction: function(id, type, description) {
        if (!this.initialized) {
            console.warn("Cannot create interaction - SCORM not initialized");
            return -1;
        }

        // Ensure valid interaction type
        var validTypes = ['true-false', 'choice', 'fill-in', 'long-fill-in', 'matching', 
                          'performance', 'sequencing', 'likert', 'numeric', 'other'];

        if (validTypes.indexOf(type) === -1) {
            console.warn("Invalid interaction type: " + type + ". Defaulting to 'other'");
            type = 'other';
        }

        // Якщо ID не вказано, генеруємо унікальний
        if (!id) {
            id = 'interaction_' + (new Date().getTime()) + '_' + (this.currentInteraction);
        }

        console.log("Creating new interaction: " + id + " of type: " + type);

        try {
            if (this.version === '2004') {
                // Встановлюємо id взаємодії
                var result = this.apiHandle.SetValue('cmi.interactions.' + this.currentInteraction + '.id', id);

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set interaction id: " + this.lastError);
                    return -1;
                }

                // Встановлюємо тип взаємодії
                if (type) {
                    result = this.apiHandle.SetValue('cmi.interactions.' + this.currentInteraction + '.type', type);

                    if (result === false) {
                        this.lastError = this.getLMSErrorMessage();
                        console.error("Failed to set interaction type: " + this.lastError);
                    }
                }

                // Встановлюємо опис взаємодії
                if (description) {
                    result = this.apiHandle.SetValue('cmi.interactions.' + this.currentInteraction + '.description', description);

                    if (result === false) {
                        this.lastError = this.getLMSErrorMessage();
                        console.error("Failed to set interaction description: " + this.lastError);
                    }
                }

                // Set timestamp for the interaction
                var timestamp = new Date().toISOString();
                this.apiHandle.SetValue('cmi.interactions.' + this.currentInteraction + '.timestamp', timestamp);

                // Повертаємо індекс взаємодії для подальшого використання
                return this.currentInteraction++;
            } else if (this.version === '1.2') {
                // У SCORM 1.2 немає description, але є id і type
                var result = this.apiHandle.LMSSetValue('cmi.interactions.' + this.currentInteraction + '.id', id);

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set interaction id: " + this.lastError);
                    return -1;
                }

                if (type) {
                    result = this.apiHandle.LMSSetValue('cmi.interactions.' + this.currentInteraction + '.type', type);

                    if (result === false) {
                        this.lastError = this.getLMSErrorMessage();
                        console.error("Failed to set interaction type: " + this.lastError);
                    }
                }

                // Record the time this interaction occurred
                // SCORM 1.2 doesn't have a timestamp for interactions, so we don't set one

                return this.currentInteraction++;
            }
        } catch (e) {
            console.error("Exception creating interaction: " + e.message);
            return -1;
        }

        return -1;
    },

    // Встановити результат взаємодії
    setInteractionResult: function(index, result) {
        if (!this.initialized || index < 0) {
            console.warn("Cannot set interaction result - SCORM not initialized or invalid index");
            return false;
        }

        // Validate result value
        var validResults = ['correct', 'incorrect', 'unanticipated', 'neutral', 'wrong'];

        // Convert wrong to incorrect for consistency
        if (result === 'wrong') {
            result = 'incorrect';
        }

        if (validResults.indexOf(result) === -1) {
            console.warn("Invalid interaction result: " + result + ". Defaulting to 'neutral'");
            result = 'neutral';
        }

        console.log("Setting result for interaction " + index + " to: " + result);

        try {
            if (this.version === '2004') {
                var setResult = this.apiHandle.SetValue('cmi.interactions.' + index + '.result', result);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set interaction result: " + this.lastError);
                }

                return setResult;
            } else if (this.version === '1.2') {
                // Map SCORM 2004 results to SCORM 1.2 format if needed
                var scorm12Results = {
                    'correct': 'correct',
                    'incorrect': 'wrong',
                    'unanticipated': 'unanticipated',
                    'neutral': 'neutral'
                };

                var mappedResult = scorm12Results[result] || 'neutral';
                var setResult = this.apiHandle.LMSSetValue('cmi.interactions.' + index + '.result', mappedResult);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set interaction result: " + this.lastError);
                }

                return setResult;
            }
        } catch (e) {
            console.error("Exception setting interaction result: " + e.message);
            return false;
        }

        return false;
    },

    // Встановити відповідь користувача на взаємодію
    setInteractionResponse: function(index, response) {
        if (!this.initialized || index < 0) {
            console.warn("Cannot set interaction response - SCORM not initialized or invalid index");
            return false;
        }

        console.log("Setting response for interaction " + index + " to: " + response);

        try {
            if (this.version === '2004') {
                var setResult = this.apiHandle.SetValue('cmi.interactions.' + index + '.learner_response', response);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set learner response: " + this.lastError);
                }

                return setResult;
            } else if (this.version === '1.2') {
                var setResult = this.apiHandle.LMSSetValue('cmi.interactions.' + index + '.student_response', response);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set student response: " + this.lastError);
                }

                return setResult;
            }
        } catch (e) {
            console.error("Exception setting interaction response: " + e.message);
            return false;
        }

        return false;
    },

    // Встановити час затримки (latency) взаємодії
    setInteractionLatency: function(index, latency) {
        if (!this.initialized || index < 0) {
            console.warn("Cannot set interaction latency - SCORM not initialized or invalid index");
            return false;
        }

        // Переконуємося, що latency у правильному форматі
        var formattedLatency;
        if (typeof latency === 'number') {
            // Конвертуємо секунди у формат PT#H#M#.#S для SCORM 2004
            // або HH:MM:SS.SS для SCORM 1.2
            if (this.version === '2004') {
                formattedLatency = this.formatTimeForSCORM2004(latency);
            } else {
                // Конвертуємо секунди у формат HH:MM:SS.SS для SCORM 1.2
                formattedLatency = this.formatTimeForSCORM12(latency);
            }
        } else {
            formattedLatency = latency; // Приймаємо as-is, якщо вже у потрібному форматі
        }

        console.log("Setting latency for interaction " + index + " to: " + formattedLatency);

        try {
            if (this.version === '2004') {
                var setResult = this.apiHandle.SetValue('cmi.interactions.' + index + '.latency', formattedLatency);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set interaction latency: " + this.lastError);
                }

                return setResult;
            } else if (this.version === '1.2') {
                var setResult = this.apiHandle.LMSSetValue('cmi.interactions.' + index + '.latency', formattedLatency);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set interaction latency: " + this.lastError);
                }

                return setResult;
            }
        } catch (e) {
            console.error("Exception setting interaction latency: " + e.message);
            return false;
        }

        return false;
    },

    // Додати правильну відповідь для взаємодії
    setInteractionCorrectResponse: function(index, correctResponse) {
        if (!this.initialized || index < 0) {
            console.warn("Cannot set correct response - SCORM not initialized or invalid index");
            return false;
        }

        console.log("Setting correct response for interaction " + index + " to: " + correctResponse);

        try {
            if (this.version === '2004') {
                var setResult = this.apiHandle.SetValue('cmi.interactions.' + index + '.correct_responses.0.pattern', correctResponse);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set correct response pattern: " + this.lastError);
                }

                return setResult;
            } else if (this.version === '1.2') {
                var setResult = this.apiHandle.LMSSetValue('cmi.interactions.' + index + '.correct_responses.0.pattern', correctResponse);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set correct response pattern: " + this.lastError);
                }

                return setResult;
            }
        } catch (e) {
            console.error("Exception setting correct response: " + e.message);
            return false;
        }

        return false;
    },

    // Додати коментар до взаємодії
    setInteractionComment: function(index, comment) {
        if (!this.initialized || index < 0 || !comment) {
            console.warn("Cannot set interaction comment - SCORM not initialized, invalid index, or empty comment");
            return false;
        }

        console.log("Setting comment for interaction " + index + " to: " + comment);

        try {
            if (this.version === '2004') {
                // У SCORM 2004 коментарі зберігаються в підмасиві comments_from_learner
                var setResult = this.apiHandle.SetValue('cmi.interactions.' + index + '.comments_from_learner.0.comment', comment);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set interaction comment: " + this.lastError);
                }

                // Add timestamp to the comment
                if (setResult) {
                    var timestamp = new Date().toISOString();
                    this.apiHandle.SetValue('cmi.interactions.' + index + '.comments_from_learner.0.timestamp', timestamp);
                    this.apiHandle.SetValue('cmi.interactions.' + index + '.comments_from_learner.0.location', 'SCORM Course');
                }

                return setResult;
            } else if (this.version === '1.2') {
                // У SCORM 1.2 немає прямої підтримки коментарів до взаємодій, використовуємо глобальні коментарі
                var currentComments = this.apiHandle.LMSGetValue('cmi.comments') || '';
                var newComment = "[Interaction " + index + "]: " + comment;

                if (currentComments) {
                    newComment = currentComments + "; " + newComment;
                }

                var setResult = this.apiHandle.LMSSetValue('cmi.comments', newComment);

                if (setResult === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set comment: " + this.lastError);
                }

                return setResult;
            }
        } catch (e) {
            console.error("Exception setting interaction comment: " + e.message);
            return false;
        }

        return false;
    },

    // ==================== СТАТИСТИКА: ЦІЛІ (OBJECTIVES) ====================

    // Додати нову ціль
    createObjective: function(id, description) {
        if (!this.initialized) {
            console.warn("Cannot create objective - SCORM not initialized");
            return -1;
        }

        // Якщо ID не вказано, генеруємо унікальний
        if (!id) {
            id = 'objective_' + (new Date().getTime()) + '_' + (this.currentObjective);
        }

        console.log("Creating new objective: " + id);

        try {
            if (this.version === '2004') {
                // Встановлюємо id цілі
                var result = this.apiHandle.SetValue('cmi.objectives.' + this.currentObjective + '.id', id);

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set objective id: " + this.lastError);
                    return -1;
                }

                // Встановлюємо опис цілі
                if (description) {
                    result = this.apiHandle.SetValue('cmi.objectives.' + this.currentObjective + '.description', description);

                    if (result === false) {
                        this.lastError = this.getLMSErrorMessage();
                        console.error("Failed to set objective description: " + this.lastError);
                    }
                }

                // Initialize required statuses
                this.apiHandle.SetValue('cmi.objectives.' + this.currentObjective + '.completion_status', 'not attempted');
                this.apiHandle.SetValue('cmi.objectives.' + this.currentObjective + '.success_status', 'unknown');

                // Повертаємо індекс цілі для подальшого використання
                return this.currentObjective++;
            } else if (this.version === '1.2') {
                // У SCORM 1.2 немає description, але є id
                var result = this.apiHandle.LMSSetValue('cmi.objectives.' + this.currentObjective + '.id', id);

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set objective id: " + this.lastError);
                    return -1;
                }

                // Initialize required statuses
                this.apiHandle.LMSSetValue('cmi.objectives.' + this.currentObjective + '.status', 'not attempted');

                return this.currentObjective++;
            }
        } catch (e) {
            console.error("Exception creating objective: " + e.message);
            return -1;
        }

        return -1;
    },

    // Встановити статус завершення цілі
    setObjectiveStatus: function(index, status) {
        if (!this.initialized || index < 0) {
            console.warn("Cannot set objective status - SCORM not initialized or invalid index");
            return false;
        }

        console.log("Setting status for objective " + index + " to: " + status);

        try {
            if (this.version === '2004') {
                var validStatuses = ['completed', 'incomplete', 'not attempted', 'unknown'];
                if (validStatuses.indexOf(status) === -1) {
                    console.warn("Invalid completion status: " + status + ". Defaulting to 'unknown'");
                    status = 'unknown';
                }

                var result = this.apiHandle.SetValue('cmi.objectives.' + index + '.completion_status', status);

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set objective completion status: " + this.lastError);
                }

                // Also set success_status if status is completed
                if (status === 'completed') {
                    this.apiHandle.SetValue('cmi.objectives.' + index + '.success_status', 'passed');
                }

                return result;
            } else if (this.version === '1.2') {
                var statusMap = {
                    'completed': 'completed',
                    'incomplete': 'incomplete',
                    'not attempted': 'not attempted',
                    'unknown': 'incomplete' // Default for unknown
                };

                var mappedStatus = statusMap[status] || status;
                var result = this.apiHandle.LMSSetValue('cmi.objectives.' + index + '.status', mappedStatus);

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set objective status: " + this.lastError);
                }

                return result;
            }
        } catch (e) {
            console.error("Exception setting objective status: " + e.message);
            return false;
        }

        return false;
    },

    // Встановити необроблену оцінку цілі (0-100)
    setObjectiveRawScore: function(index, score) {
        if (!this.initialized || index < 0) {
            console.warn("Cannot set objective raw score - SCORM not initialized or invalid index");
            return false;
        }

        // Ensure score is a number between 0 and 100
        if (typeof score !== 'number') {
            try {
                score = parseFloat(score);
            } catch (e) {
                console.error("Invalid score value, must be a number: " + score);
                return false;
            }
        }

        score = Math.max(0, Math.min(100, score));

        console.log("Setting raw score for objective " + index + " to: " + score);

        try {
            if (this.version === '2004') {
                var result = this.apiHandle.SetValue('cmi.objectives.' + index + '.score.raw', score.toString());

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set objective raw score: " + this.lastError);
                }

                // Also set min and max score for context
                this.apiHandle.SetValue('cmi.objectives.' + index + '.score.min', '0');
                this.apiHandle.SetValue('cmi.objectives.' + index + '.score.max', '100');

                return result;
            } else if (this.version === '1.2') {
                var result = this.apiHandle.LMSSetValue('cmi.objectives.' + index + '.score.raw', score.toString());

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set objective raw score: " + this.lastError);
                }

                // Also set min and max score for context
                this.apiHandle.LMSSetValue('cmi.objectives.' + index + '.score.min', '0');
                this.apiHandle.LMSSetValue('cmi.objectives.' + index + '.score.max', '100');

                return result;
            }
        } catch (e) {
            console.error("Exception setting objective raw score: " + e.message);
            return false;
        }

        return false;
    },

    // Встановити масштабовану оцінку цілі (0-1)
    setObjectiveScaledScore: function(index, score) {
        if (!this.initialized || index < 0) {
            console.warn("Cannot set objective scaled score - SCORM not initialized or invalid index");
            return false;
        }

        // Ensure score is a number between 0 and 1
        if (typeof score !== 'number') {
            try {
                score = parseFloat(score);
            } catch (e) {
                console.error("Invalid score value, must be a number: " + score);
                return false;
            }
        }

        score = Math.max(0, Math.min(1, score));

        console.log("Setting scaled score for objective " + index + " to: " + score);

        try {
            if (this.version === '2004') {
                var result = this.apiHandle.SetValue('cmi.objectives.' + index + '.score.scaled', score.toString());

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set objective scaled score: " + this.lastError);
                }

                // Also set raw score (0-100) for consistency
                this.apiHandle.SetValue('cmi.objectives.' + index + '.score.raw', Math.round(score * 100).toString());
                this.apiHandle.SetValue('cmi.objectives.' + index + '.score.min', '0');
                this.apiHandle.SetValue('cmi.objectives.' + index + '.score.max', '100');

                // Set success_status based on scaled score
                if (score >= 0.7) {
                    this.apiHandle.SetValue('cmi.objectives.' + index + '.success_status', 'passed');
                } else if (score > 0) {
                    this.apiHandle.SetValue('cmi.objectives.' + index + '.success_status', 'failed');
                }

                return result;
            } else if (this.version === '1.2') {
                // У SCORM 1.2 немає масштабованої оцінки, тому конвертуємо в raw 0-100
                var rawScore = Math.round(score * 100);
                var result = this.apiHandle.LMSSetValue('cmi.objectives.' + index + '.score.raw', rawScore.toString());

                if (result === false) {
                    this.lastError = this.getLMSErrorMessage();
                    console.error("Failed to set objective score: " + this.lastError);
                }

                // Set min and max scores
                this.apiHandle.LMSSetValue('cmi.objectives.' + index + '.score.min', '0');
                this.apiHandle.LMSSetValue('cmi.objectives.' + index + '.score.max', '100');

                // Set status based on score
                if (score >= 0.7) {
                    this.apiHandle.LMSSetValue('cmi.objectives.' + index + '.status', 'passed');
                } else if (score > 0) {
                    this.apiHandle.LMSSetValue('cmi.objectives.' + index + '.status', 'failed');
                }

                return result;
            }
        } catch (e) {
            console.error("Exception setting objective scaled score: " + e.message);
            return false;
        }

        return false;
    },

    // ==================== Допоміжні функції ====================

    // Форматує час у форматі SCORM 2004 (PT#H#M#.#S)
    formatTimeForSCORM2004: function(seconds) {
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = Math.floor(seconds % 60);
        var ms = Math.round((seconds % 1) * 100);

        var result = 'PT';
        if (h > 0) result += h + 'H';
        if (m > 0) result += m + 'M';
        if (s > 0 || (h === 0 && m === 0)) {
            if (ms > 0) {
                result += s + '.' + (ms < 10 ? '0' + ms : ms) + 'S';
            } else {
                result += s + 'S';
            }
        }

        return result;
    },

    // Форматує час у форматі SCORM 1.2 (HH:MM:SS.SS)
    formatTimeForSCORM12: function(seconds) {
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = Math.floor(seconds % 60);
        var ms = Math.round((seconds % 1) * 100);

        var hStr = (h < 10 ? '0' : '') + h;
        var mStr = (m < 10 ? '0' : '') + m;
        var sStr = (s < 10 ? '0' : '') + s;
        var msStr = (ms < 10 ? '0' : '') + ms;

        return hStr + ':' + mStr + ':' + sStr + '.' + msStr;
    },

    // Пошук API в ієрархії фреймів
    getAPI: function() {
        var win = window;
        var findAPITries = 0;
        var findAPIMaxTries = 10;

        console.log("Searching for SCORM API in parent frames...");

        // Спочатку шукаємо SCORM 2004 API
        while ((win.API_1484_11 == null) && (win.parent != null) && (win.parent != win) && (findAPITries < findAPIMaxTries)) {
            findAPITries++;
            win = win.parent;
        }

        // Check if API_1484_11 is found
        if (win.API_1484_11) {
            console.log("Found SCORM 2004 API at attempt " + findAPITries);
            return win.API_1484_11;
        }

        // Якщо не знайшли, шукаємо SCORM 1.2 API
        win = window;
        findAPITries = 0;

        while ((win.API == null) && (win.parent != null) && (win.parent != win) && (findAPITries < findAPIMaxTries)) {
            findAPITries++;
            win = win.parent;
        }

        // Check if API is found
        if (win.API) {
            console.log("Found SCORM 1.2 API at attempt " + findAPITries);
            return win.API;
        }

        // Additional search in opener window (for popup scenarios)
        if (window.opener != null && typeof window.opener != "undefined") {
            console.log("Searching for SCORM API in opener window...");

            // Check for SCORM 2004 API in opener
            if (window.opener.API_1484_11) {
                return window.opener.API_1484_11;
            }

            // Check for SCORM 1.2 API in opener
            if (window.opener.API) {
                return window.opener.API;
            }
        }

        console.warn("SCORM API not found after " + findAPIMaxTries + " attempts");
        return null;
    }
};

// ==================== Допоміжні утиліти для трекінгу ====================

var SCORMTracker = {
    // Відстеження часу
    startTime: new Date(),
    sessionStartTime: new Date(), // For session time tracking
    interactionTimers: {}, // Для відстеження часу взаємодій
    totalTimeSpent: 0, // Total accumulated time

    // Записати новий квіз
    startQuiz: function(quizId, quizTitle) {
        if (!SCORM.initialized) return -1;

        console.log("Starting quiz tracking: " + quizId + " - " + quizTitle);
        var objectiveIndex = SCORM.createObjective(quizId, quizTitle);

        if (objectiveIndex >= 0) {
            // Set initial status for the objective
            SCORM.setObjectiveStatus(objectiveIndex, 'incomplete');

            // Add interaction for quiz start
            var interactionId = "quiz_start_" + quizId;
            var interactionIndex = SCORM.createInteraction(interactionId, 'other', 'Started quiz: ' + quizTitle);
            SCORM.setInteractionResponse(interactionIndex, 'started');
            SCORM.setInteractionResult(interactionIndex, 'neutral');

            // Commit changes
            SCORM.commit();
        }

        return objectiveIndex;
    },

    // Записати питання у квізі
    startQuestion: function(questionId, questionType, questionText) {
        if (!SCORM.initialized) return -1;

        console.log("Starting question tracking: " + questionId + " - " + questionText);
        var interactionIndex = SCORM.createInteraction(questionId, questionType, questionText);

        // Засікаємо час початку роботи з питанням
        if (interactionIndex >= 0) {
            this.interactionTimers[interactionIndex] = new Date();
        }

        return interactionIndex;
    },

    // Записати відповідь на питання
    recordAnswer: function(interactionIndex, userResponse, correctResponse, isCorrect) {
        if (!SCORM.initialized || interactionIndex < 0) return false;

        console.log("Recording answer for interaction " + interactionIndex + ": " + userResponse + 
                    " (Correct: " + correctResponse + ", Result: " + (isCorrect ? "correct" : "incorrect") + ")");

        // Розраховуємо час, витрачений на відповідь (latency)
        var now = new Date();
        var latency = 0;

        if (this.interactionTimers[interactionIndex]) {
            latency = (now - this.interactionTimers[interactionIndex]) / 1000; // у секундах
        }

        // Записуємо відповідь
        SCORM.setInteractionResponse(interactionIndex, userResponse);

        // Set the correct response pattern
        if (correctResponse) {
            SCORM.setInteractionCorrectResponse(interactionIndex, correctResponse);
        }

        // Записуємо результат (correct, incorrect, neutral)
        var result = isCorrect ? 'correct' : 'incorrect';
        SCORM.setInteractionResult(interactionIndex, result);

        // Записуємо latency
        if (latency > 0) {
            SCORM.setInteractionLatency(interactionIndex, latency);
        }

        // Фіксуємо зміни
        SCORM.commit();

        return true;
    },

    // Завершити квіз із результатом
    finishQuiz: function(objectiveIndex, score, maxScore) {
        if (!SCORM.initialized || objectiveIndex < 0) return false;

        // Validate score values
        if (typeof score !== 'number' || typeof maxScore !== 'number' || maxScore <= 0) {
            console.error("Invalid score values. Score: " + score + ", Max Score: " + maxScore);
            return false;
        }

        console.log("Finishing quiz with score: " + score + "/" + maxScore);

        // Розраховуємо масштабовану оцінку (0-1)
        var scaledScore = score / maxScore;

        // Записуємо "сиру" оцінку
        SCORM.setObjectiveRawScore(objectiveIndex, score);

        // Записуємо масштабовану оцінку
        SCORM.setObjectiveScaledScore(objectiveIndex, scaledScore);

        // Встановлюємо статус завершення квізу
        var status = score >= (maxScore * 0.6) ? 'completed' : 'incomplete';
        SCORM.setObjectiveStatus(objectiveIndex, status);

        // Add interaction for quiz completion
        var interactionId = "quiz_finish_" + objectiveIndex;
        var interactionIndex = SCORM.createInteraction(interactionId, 'numeric', 'Completed quiz with score: ' + score + '/' + maxScore);
        SCORM.setInteractionResponse(interactionIndex, score.toString());
        SCORM.setInteractionResult(interactionIndex, status === 'completed' ? 'correct' : 'incorrect');

        // Фіксуємо зміни
        SCORM.commit();

        return true;
    },

    // Записати загальний прогрес проходження курсу
    updateProgress: function(progress) {
        if (!SCORM.initialized) return false;

        // Обмежуємо прогрес діапазоном [0, 1]
        progress = Math.max(0, Math.min(1, progress));

        console.log("Updating course progress: " + (progress * 100) + "%");

        // Встановлюємо прогрес
        SCORM.setProgressMeasure(progress);

        // Якщо прогрес досяг 100%, позначаємо курс як завершений
        if (progress >= 0.99) {
            console.log("Progress reached 100%, marking course as completed");
            SCORM.setCompletionStatus("completed");

            // Add interaction for course completion
            var interactionId = "course_complete";
            var interactionIndex = SCORM.createInteraction(interactionId, 'true-false', 'Course completed');
            SCORM.setInteractionResponse(interactionIndex, 'true');
            SCORM.setInteractionResult(interactionIndex, 'correct');
        }

        // Фіксація змін у LMS
        SCORM.commit();

        return true;
    },

    // Tracking page views
    recordPageView: function(pageId, pageTitle) {
        if (!SCORM.initialized) return -1;

        console.log("Recording page view: " + pageId + " - " + pageTitle);

        // Create interaction for page view
        var interactionId = "page_view_" + pageId;
        var interactionIndex = SCORM.createInteraction(interactionId, 'other', 'Viewed page: ' + pageTitle);

        if (interactionIndex >= 0) {
            SCORM.setInteractionResponse(interactionIndex, 'viewed');
            SCORM.setInteractionResult(interactionIndex, 'neutral');

            // Commit changes
            SCORM.commit();
        }

        return interactionIndex;
    },

    // Track specific user actions/events
    recordUserAction: function(actionId, actionType, actionDescription, actionDetail) {
        if (!SCORM.initialized) return -1;

        console.log("Recording user action: " + actionId + " - " + actionDescription);

        // Create interaction for user action
        var interactionId = "action_" + actionId;
        var interactionIndex = SCORM.createInteraction(interactionId, actionType || 'other', actionDescription);

        if (interactionIndex >= 0) {
            SCORM.setInteractionResponse(interactionIndex, actionDetail || 'performed');
            SCORM.setInteractionResult(interactionIndex, 'neutral');

            // Commit changes
            SCORM.commit();
        }

        return interactionIndex;
    },

    // Отримання тривалості сесії в секундах
    getSessionDuration: function() {
        var currentTime = new Date();
        var sessionDuration = Math.floor((currentTime - this.sessionStartTime) / 1000);
        return sessionDuration;
    },

    // Отримання загального часу в секундах
    getTotalDuration: function() {
        var currentTime = new Date();
        var currentSession = Math.floor((currentTime - this.sessionStartTime) / 1000);
        return this.totalTimeSpent + currentSession;
    },

    // Оновлення часу сесії в SCORM
    updateSessionTime: function() {
        if (!SCORM.initialized) return false;

        try {
            var duration = this.getSessionDuration();
            console.log("Updating session time: " + duration + " seconds");

            if (SCORM.version === '2004') {
                var formattedTime = SCORM.formatTimeForSCORM2004(duration);
                SCORM.apiHandle.SetValue('cmi.session_time', formattedTime);

                // Get total time from LMS if available
                var totalTime = SCORM.apiHandle.GetValue('cmi.total_time');
                if (totalTime && totalTime !== '') {
                    console.log("Total time from LMS: " + totalTime);
                }
            } else if (SCORM.version === '1.2') {
                var formattedTime = SCORM.formatTimeForSCORM12(duration);
                SCORM.apiHandle.LMSSetValue('cmi.core.session_time', formattedTime);

                // In SCORM 1.2, we can't directly get total_time
            }

            // Update total time tracking
            this.totalTimeSpent += duration;
            this.sessionStartTime = new Date();

            // Commit changes
            SCORM.commit();
            return true;
        } catch (e) {
            console.error("Error updating session time: " + e.message);
            return false;
        }
    },

    // Додавання коментаря від студента
    addComment: function(comment, location) {
        if (!SCORM.initialized || !comment) return false;

        try {
            console.log("Adding learner comment: " + comment);

            if (SCORM.version === '2004') {
                // Get current comment count
                var count = 0;
                var countStr = SCORM.apiHandle.GetValue('cmi.comments_from_learner._count');
                if (countStr && !isNaN(parseInt(countStr))) {
                    count = parseInt(countStr);
                }

                // Add new comment
                SCORM.apiHandle.SetValue('cmi.comments_from_learner.' + count + '.comment', comment);
                SCORM.apiHandle.SetValue('cmi.comments_from_learner.' + count + '.location', location || 'SCORM Course');
                SCORM.apiHandle.SetValue('cmi.comments_from_learner.' + count + '.timestamp', new Date().toISOString());
            } else if (SCORM.version === '1.2') {
                // In SCORM 1.2, there is only one comments field
                var currentComments = SCORM.apiHandle.LMSGetValue('cmi.comments') || '';
                var newComment = comment;

                if (currentComments) {
                    newComment = currentComments + "; " + newComment;
                }

                SCORM.apiHandle.LMSSetValue('cmi.comments', newComment);
            }

            // Commit changes
            SCORM.commit();
            return true;
        } catch (e) {
            console.error("Error adding comment: " + e.message);
            return false;
        }
    },

    // Reset tracking for a new attempt
    resetTracking: function() {
        if (!SCORM.initialized) return false;

        try {
            console.log("Resetting tracking data for new attempt");

            // Reset timers
            this.startTime = new Date();
            this.sessionStartTime = new Date();
            this.interactionTimers = {};
            this.totalTimeSpent = 0;

            // Reset interaction and objective counters in SCORM
            SCORM.currentInteraction = 0;
            SCORM.currentObjective = 0;

            // Set initial statuses in SCORM
            if (SCORM.version === '2004') {
                SCORM.apiHandle.SetValue('cmi.completion_status', 'incomplete');
                SCORM.apiHandle.SetValue('cmi.success_status', 'unknown');
                SCORM.apiHandle.SetValue('cmi.progress_measure', '0');
                SCORM.apiHandle.SetValue('cmi.score.scaled', '0');
            } else if (SCORM.version === '1.2') {
                SCORM.apiHandle.LMSSetValue('cmi.core.lesson_status', 'incomplete');
                SCORM.apiHandle.LMSSetValue('cmi.core.score.raw', '0');
            }

            // Commit changes
            SCORM.commit();
            return true;
        } catch (e) {
            console.error("Error resetting tracking: " + e.message);
            return false;
        }
    }
};

// Глобальні функції для виклику з HTML
function initializeSCORM() {
    console.log("Initializing SCORM tracking...");
    var success = SCORM.init();

    if (success) {
        console.log("SCORM initialized successfully");

        // Register window unload event to ensure proper termination
        window.addEventListener('beforeunload', function() {
            terminateSCORM();
        });

        // Create a setInterval to regularly update session time and commit data
        setInterval(function() {
            if (SCORM.initialized) {
                SCORMTracker.updateSessionTime();
            }
        }, 60000); // Every minute

        return true;
    } else {
        console.error("Failed to initialize SCORM");
        return false;
    }
}

function terminateSCORM() {
    console.log("Terminating SCORM session...");

    // Update session time before terminating
    if (typeof SCORMTracker !== 'undefined' && SCORM.initialized) {
        SCORMTracker.updateSessionTime();
    }

    // Terminate SCORM session
    if (typeof SCORM !== 'undefined' && SCORM.initialized) {
        SCORM.terminate();
    }
}

// Функції для квізів і питань
function trackQuizStart(quizId, quizTitle) {
    return SCORMTracker.startQuiz(quizId, quizTitle);
}

function trackQuestion(questionId, questionType, questionText) {
    return SCORMTracker.startQuestion(questionId, questionType, questionText);
}

function trackAnswer(interactionIndex, userResponse, correctResponse, isCorrect) {
    return SCORMTracker.recordAnswer(interactionIndex, userResponse, correctResponse, isCorrect);
}

function trackQuizResult(objectiveIndex, score, maxScore) {
    return SCORMTracker.finishQuiz(objectiveIndex, score, maxScore);
}

function updateCourseProgress(progress) {
    return SCORMTracker.updateProgress(progress);
}

function trackPageView(pageId, pageTitle) {
    return SCORMTracker.recordPageView(pageId, pageTitle);
}

function trackUserAction(actionId, actionType, actionDescription, actionDetail) {
    return SCORMTracker.recordUserAction(actionId, actionType, actionDescription, actionDetail);
}

function addUserComment(comment, location) {
    return SCORMTracker.addComment(comment, location);
}

// Auto-initialize if running in a SCORM environment
(function() {
    // Check if we're in a frameset that might contain SCORM API
    if (window.parent !== window) {
        console.log("Detected potential SCORM environment, attempting auto-initialization");

        // Add a slight delay to ensure the API is loaded
        setTimeout(function() {
            initializeSCORM();
        }, 500);
    }
})();"""

    js_path = os.path.join(content_dir, 'scorm_api.js')

    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)

    return 'scorm_api.js'


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


def add_aws_signature_script(soup, access_key, secret_key, region='auto', service='s3'):
    """
    Додає скрипт для підписування запитів до S3/Cloudflare R2 за стандартом AWS Signature V4
    """
    script_content = f"""
// AWS Signature V4 Helper
class AWSV4Signer {{
    constructor(accessKey, secretKey, region, service) {{
        this.accessKey = accessKey;
        this.secretKey = secretKey;
        this.region = region;
        this.service = service;
    }}

    // Підписування URL для GET-запитів
    signUrl(url, expires = 300) {{
        const urlObj = new URL(url);
        const host = urlObj.host;
        const path = urlObj.pathname;

        // Поточний час в ISO форматі
        const dateTimeNow = new Date().toISOString().replace(/[:-]|\\.\\d{3}/g, '');
        const dateNow = dateTimeNow.substr(0, 8);

        // Базові параметри
        const queryParams = {{
            'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
            'X-Amz-Credential': `${{this.accessKey}}/${{dateNow}}/${{this.region}}/${{this.service}}/aws4_request`,
            'X-Amz-Date': dateTimeNow,
            'X-Amz-Expires': expires.toString(),
            'X-Amz-SignedHeaders': 'host'
        }};

        // Додаємо параметри до URL
        Object.keys(queryParams).forEach(key => {{
            urlObj.searchParams.append(key, queryParams[key]);
        }});

        // Створення канонічного запиту
        const canonicalRequest = [
            'GET',
            path,
            urlObj.search.substr(1), // Параметри запиту без '?'
            `host:${{host}}\\n`,
            'host',
            'UNSIGNED-PAYLOAD'
        ].join('\\n');

        // Створення строки для підпису
        const stringToSign = [
            'AWS4-HMAC-SHA256',
            dateTimeNow,
            `${{dateNow}}/${{this.region}}/${{this.service}}/aws4_request`,
            this.sha256(canonicalRequest)
        ].join('\\n');

        // Генерація ключа підпису
        const signingKey = this.getSignatureKey(this.secretKey, dateNow, this.region, this.service);

        // Підписування
        const signature = this.hmacSha256Hex(signingKey, stringToSign);

        // Додавання підпису до URL
        urlObj.searchParams.append('X-Amz-Signature', signature);

        return urlObj.toString();
    }}

    // Допоміжні функції для криптографії (використовуємо вбудовані у браузер WebCrypto API)
    async sha256(message) {{
        const msgBuffer = new TextEncoder().encode(message);
        const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
        return Array.from(new Uint8Array(hashBuffer))
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
    }}

    async hmacSha256(key, message) {{
        const keyBuffer = typeof key === 'string' ? new TextEncoder().encode(key) : key;
        const messageBuffer = new TextEncoder().encode(message);

        const cryptoKey = await crypto.subtle.importKey(
            'raw', keyBuffer, {{ name: 'HMAC', hash: 'SHA-256' }}, false, ['sign']
        );

        const signature = await crypto.subtle.sign('HMAC', cryptoKey, messageBuffer);
        return new Uint8Array(signature);
    }}

    async hmacSha256Hex(key, message) {{
        const signature = await this.hmacSha256(key, message);
        return Array.from(signature)
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
    }}

    async getSignatureKey(key, dateStamp, region, service) {{
        const kDate = await this.hmacSha256('AWS4' + key, dateStamp);
        const kRegion = await this.hmacSha256(kDate, region);
        const kService = await this.hmacSha256(kRegion, service);
        const kSigning = await this.hmacSha256(kService, 'aws4_request');
        return kSigning;
    }}
}}

// Створення підписувача
const awsSigner = new AWSV4Signer(
    '{access_key}', // Access Key
    '{secret_key}', // Secret Key
    '{region}',     // Region
    '{service}'     // Service
);

// Заміна fetch для автоматичного підписування
const originalFetch = window.fetch;
window.fetch = async function(resource, options) {{
    // Перевіряємо, чи URL вказує на Cloudflare/S3
    const url = resource instanceof Request ? resource.url : resource;
    if (typeof url === 'string' && 
        (url.includes('cloudflare') || url.includes('amazonaws') || url.includes('s3.'))) {{
        // Підписуємо URL
        const signedUrl = await awsSigner.signUrl(url);

        // Створюємо новий Request, якщо вхідний ресурс був Request
        if (resource instanceof Request) {{
            const newRequest = new Request(signedUrl, resource);
            return originalFetch(newRequest, options);
        }}

        // Інакше просто використовуємо підписаний URL
        return originalFetch(signedUrl, options);
    }}

    // Для інших запитів використовуємо оригінальний fetch
    return originalFetch(resource, options);
}};

// Заміна XMLHttpRequest для автоматичного підписування
const originalXHROpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = async function(method, url, async, user, password) {{
    if (typeof url === 'string' && 
        (url.includes('cloudflare') || url.includes('amazonaws') || url.includes('s3.'))) {{
        // Підписуємо URL
        const signedUrl = await awsSigner.signUrl(url);
        return originalXHROpen.call(this, method, signedUrl, async, user, password);
    }}
    return originalXHROpen.call(this, method, url, async, user, password);
}};

// Заміна атрибутів src/href для зображень, скриптів тощо
function replaceExternalResourceUrls() {{
    // Функція для перевірки та заміни URL
    async function checkAndReplaceUrl(element, attribute) {{
        const url = element.getAttribute(attribute);
        if (url && (url.includes('cloudflare') || url.includes('amazonaws') || url.includes('s3.'))) {{
            try {{
                const signedUrl = await awsSigner.signUrl(url);
                element.setAttribute(attribute, signedUrl);
                console.log(`Підписано URL для ${{element.tagName}}: ${{url}}`);
            }} catch (e) {{
                console.error(`Помилка підписування URL: ${{e.message}}`);
            }}
        }}
    }}

    // Обробка всіх зображень
    document.querySelectorAll('img[src]').forEach(img => 
        checkAndReplaceUrl(img, 'src'));

    // Обробка всіх скриптів
    document.querySelectorAll('script[src]').forEach(script => 
        checkAndReplaceUrl(script, 'src'));

    // Обробка всіх стилів
    document.querySelectorAll('link[href]').forEach(link => 
        checkAndReplaceUrl(link, 'href'));
}}

// Запуск функції заміни URL при завантаженні сторінки
window.addEventListener('DOMContentLoaded', replaceExternalResourceUrls);
    """

    # Замінюємо ключі підстановкою
    script_content = script_content.replace('{access_key}', access_key)
    script_content = script_content.replace('{secret_key}', secret_key)
    script_content = script_content.replace('{region}', region)
    script_content = script_content.replace('{service}', service)

    # Додаємо скрипт до head
    head = soup.find('head')
    if head:
        aws_script = soup.new_tag('script')
        aws_script.string = script_content
        head.append(aws_script)
        print("Додано скрипт для підписування запитів до AWS/Cloudflare")

    return soup


def main():
    """
    Головна функція для конвертування файлів у SCORM-пакети
    """
    parser = argparse.ArgumentParser(description='Конвертер для роботи зі SCORM-пакетами')
    parser.add_argument('input_file', nargs='?', help='Шлях до вхідного файлу (HTML файл або SCORM-пакет)')
    parser.add_argument('--output', '-o', help='Шлях до вихідного файлу')
    parser.add_argument('--title', '-t', help='Назва курсу (для конвертації в SCORM)')
    parser.add_argument('--scorm-version', '-v', choices=['1.2', '2004'], default='2004',
                        help='Версія SCORM (1.2 або 2004)')

    args = parser.parse_args()

    # Якщо файл не вказано, показуємо список файлів у поточній директорії
    if not args.input_file:
        print("=== SCORM КОНВЕРТЕР ===")
        print("Цей скрипт конвертує HTML-файли в SCORM-пакети та навпаки\n")

        # Збираємо список файлів у поточній директорії
        supported_extensions = ('.html', '.htm', '.zip', '.scorm')
        current_files = [f for f in os.listdir('.') if os.path.isfile(f) and
                         f.lower().endswith(supported_extensions)]

        if current_files:
            print("Знайдено підтримувані файли в поточній директорії:")
            for i, file in enumerate(current_files, 1):
                file_type = "HTML" if file.lower().endswith(('.html', '.htm')) else "SCORM"
                print(f"{i}. {file} ({file_type})")
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
            args.input_file = input("Введіть шлях до файлу (HTML або SCORM): ").strip()

    # Перевірка наявності файлу
    if not os.path.exists(args.input_file):
        print(f"Помилка: Файл '{args.input_file}' не знайдено")
        sys.exit(1)

    # Визначення типу файлу
    is_scorm = args.input_file.lower().endswith(('.zip', '.scorm'))
    is_html = args.input_file.lower().endswith(('.html', '.htm'))

    if not (is_scorm or is_html):
        print("Помилка: Непідтримуваний тип файлу")
        print("Підтримувані формати: HTML, HTM, ZIP, SCORM")
        sys.exit(1)

    # Вибір операції
    if not (args.extract or args.convert_to_html or args.analyze):
        if is_scorm:
            print("\nВиберіть операцію для SCORM-пакету:")
            print("1. Конвертувати SCORM-пакет в HTML")

            choice = input("Ваш вибір (1-3): ").strip()
            if choice == '1':
                args.convert_to_html = True
            else:
                print("Помилка: Невідома операція")
                sys.exit(1)
        else:  # is_html
            # Якщо це HTML, конвертуємо його в SCORM за замовчуванням
            pass

    else:  # is_html
        # Конвертація HTML в SCORM
        if not args.output:
            output_path = os.path.splitext(args.input_file)[0] + "_scorm.zip"
            confirm = input(f"Конвертувати HTML-файл в SCORM-пакет '{output_path}'? (y/n) [y]: ").strip().lower()
            if confirm != 'n':
                args.output = output_path
            else:
                args.output = input("Введіть шлях для збереження SCORM-пакету: ").strip()

        # Запитуємо назву курсу, якщо не вказано
        if not args.title:
            try:
                with open(args.input_file, 'r', encoding='utf-8', errors='ignore') as f:
                    html_content = f.read()
                soup = BeautifulSoup(html_content, 'html.parser')
                title_tag = soup.find('title')
                default_title = title_tag.string.strip() if title_tag and title_tag.string else \
                os.path.splitext(os.path.basename(args.input_file))[0]
            except:
                default_title = os.path.splitext(os.path.basename(args.input_file))[0]

            args.title = input(f"Назва курсу [{default_title}]: ").strip() or default_title

        print(f"\nКонвертація HTML-файлу {args.input_file} в SCORM-пакет...")
        result = convert_html_to_scorm(
            args.input_file,
            args.output,
            args.title,
            args.scorm_version,
            not args.no_resources
        )

        if result:
            print(f"HTML-файл успішно конвертовано в SCORM-пакет: {args.output}")
        else:
            print("Помилка при конвертації HTML в SCORM")
            sys.exit(1)


if __name__ == "__main__":
    main()