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


def extract_pdfs_from_scorm(scorm_path, output_dir=None, output_pdf=None):
    """
    Витягує PDF-файли зі SCORM-пакету

    Args:
        scorm_path (str): Шлях до SCORM-пакету (.zip)
        output_dir (str): Директорія для збереження PDF-файлів
        output_pdf (str): Шлях для основного PDF-файлу, якщо буде один файл

    Returns:
        list: Список шляхів до витягнутих PDF-файлів
    """
    try:
        # Визначення вихідної директорії
        if not output_dir:
            output_dir = os.path.dirname(scorm_path) or '.'

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Створення тимчасової директорії для розпакування
        temp_dir = tempfile.mkdtemp()

        # Розпакування SCORM-пакету
        print(f"Розпакування SCORM-пакету: {scorm_path}")
        with zipfile.ZipFile(scorm_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Пошук маніфесту для аналізу структури
        manifest_path = os.path.join(temp_dir, 'imsmanifest.xml')
        scorm_title = 'SCORM Course'

        if os.path.exists(manifest_path):
            # Парсинг маніфесту для отримання назви курсу
            tree = ET.parse(manifest_path)
            root = tree.getroot()

            # Пошук заголовку курсу
            title_elems = root.findall('.//title') + root.findall('.//{*}title')
            for title_elem in title_elems:
                if title_elem.text and title_elem.text.strip():
                    scorm_title = title_elem.text.strip()
                    break

        # Пошук PDF-файлів в розпакованому пакеті
        print("Пошук PDF-файлів...")
        pdf_files = []

        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_path = os.path.join(root, file)

                    # Визначення імені для збереження
                    pdf_name = file

                    # Якщо є один PDF і вказано вихідний файл
                    if output_pdf and len(pdf_files) == 0:
                        target_path = output_pdf
                    else:
                        # Уникнення конфліктів імен
                        counter = 1
                        base_name = os.path.splitext(pdf_name)[0]
                        ext = os.path.splitext(pdf_name)[1]
                        target_path = os.path.join(output_dir, pdf_name)

                        while os.path.exists(target_path):
                            pdf_name = f"{base_name}_{counter}{ext}"
                            target_path = os.path.join(output_dir, pdf_name)
                            counter += 1

                    # Копіювання файлу
                    shutil.copy2(pdf_path, target_path)
                    pdf_files.append(target_path)
                    print(f"Витягнуто PDF: {target_path}")

        # Пошук HTML-файлів, якщо не знайдено PDF
        if not pdf_files:
            html_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(('.html', '.htm')):
                        html_files.append(os.path.join(root, file))

            if html_files:
                print("\nЗнайдено HTML-файли, але не знайдено PDF.")
                print("Для конвертації HTML в PDF потрібні додаткові бібліотеки:")
                print("1. Встановіть GTK+ для macOS: brew install gtk+")
                print("2. Встановіть Pango: brew install pango")
                print("3. Встановіть WeasyPrint: pip install weasyprint")
            else:
                print("\nНе знайдено ні PDF, ні HTML файлів у SCORM-пакеті.")

        # Очищення тимчасових файлів
        shutil.rmtree(temp_dir)

        return pdf_files

    except Exception as e:
        print(f"Помилка при обробці SCORM: {e}")
        # Спроба очистити тимчасові файли у випадку помилки
        try:
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
        return []


def main():
    """
    Головна функція для конвертації SCORM в PDF
    """
    parser = argparse.ArgumentParser(description='Витягнення PDF з SCORM-пакету')
    parser.add_argument('input_file', nargs='?', help='Шлях до SCORM-пакету (.zip)')
    parser.add_argument('--output', '-o', help='Шлях для збереження PDF-файлу')
    parser.add_argument('--output-dir', '-d', help='Директорія для збереження витягнутих PDF-файлів')

    args = parser.parse_args()

    # Якщо шлях до файлу не вказано через аргументи, запитуємо його
    if not args.input_file:
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

    # Вихідний файл
    if not args.output and not args.output_dir:
        output_dir = os.path.dirname(args.input_file) or '.'
        output_name = os.path.splitext(os.path.basename(args.input_file))[0]
        default_output = os.path.join(output_dir, f"{output_name}.pdf")
        output_input = input(
            f"Шлях до вихідного PDF-файлу (або залиште порожнім для автоматичного іменування): ").strip()
        args.output = output_input or default_output

    print("\nПочинаю обробку SCORM-пакету...")

    # Викликаємо функцію обробки
    pdf_files = extract_pdfs_from_scorm(args.input_file, args.output_dir, args.output)

    if pdf_files:
        print(f"\nУспішно витягнуто {len(pdf_files)} PDF-файлів.")
    else:
        print("\nНе вдалося витягнути PDF-файли з SCORM-пакету.")
        sys.exit(1)


if __name__ == "__main__":
    main()