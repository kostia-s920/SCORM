#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
from docx_converter import convert_docx_to_scorm
from pdf_converter import convert_pdf_to_scorm
from html_converter import convert_html_to_scorm


def main():
    """
    Головна функція для запу ску конвертера різних типів файлів у SCORM-формат
    """
    parser = argparse.ArgumentParser(description='Конвертер навчальних матеріалів у SCORM-формат')
    parser.add_argument('input_file', nargs='?', help='Шлях до вхідного файлу (PDF, DOCX, HTML)')
    parser.add_argument('--output', '-o', help='Шлях до вихідного SCORM-пакету (.zip)')
    parser.add_argument('--title', '-t', help='Назва курсу (за замовчуванням - назва вхідного файлу)')
    parser.add_argument('--scorm-version', '-v', choices=['1.2', '2004'], default='2004',
                        help='Версія SCORM (1.2 або 2004)')
    parser.add_argument('--no-resources', '-n', action='store_true',
                        help='Не включати пов\'язані ресурси для HTML (CSS, зображення тощо)')

    args = parser.parse_args()

    # Якщо шлях до файлу не вказано через аргументи, запитуємо його
    if not args.input_file:
        print("=== SCORM CONVERTER ===")
        print("Цей скрипт конвертує PDF, DOCX або HTML документи у SCORM-пакети\n")

        # Показуємо список файлів у поточній директорії
        current_files = [f for f in os.listdir('.') if os.path.isfile(f) and
                         f.lower().endswith(('.pdf', '.docx', '.doc', '.html', '.htm'))]

        if current_files:
            print("Знайдено документи в поточній директорії:")
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
            args.input_file = input("Введіть шлях до файлу (PDF, DOCX або HTML): ").strip()

    # Перевірка наявності файлу
    while not os.path.exists(args.input_file):
        print(f"Помилка: Файл '{args.input_file}' не знайдено")
        args.input_file = input("Введіть правильний шлях до файлу: ").strip()
        # Якщо користувач ввів порожній рядок, виходимо
        if not args.input_file:
            print("Операцію скасовано.")
            sys.exit(0)

    # Визначення типу файлу
    file_extension = os.path.splitext(args.input_file)[1].lower()

    if file_extension not in ['.pdf', '.docx', '.doc', '.html', '.htm']:
        print(f"Помилка: Непідтримуваний тип файлу '{file_extension}'")
        print("Підтримувані формати: PDF, DOCX, DOC, HTML, HTM")
        sys.exit(1)

    # Запитуємо додаткові параметри, якщо вони не вказані

    # Назва курсу
    if not args.title:
        default_title = os.path.splitext(os.path.basename(args.input_file))[0]

        # Спроба отримати заголовок з HTML-файлу
        if file_extension in ['.html', '.htm']:
            try:
                from bs4 import BeautifulSoup
                with open(args.input_file, 'r', encoding='utf-8', errors='ignore') as f:
                    html_content = f.read()
                soup = BeautifulSoup(html_content, 'html.parser')
                title_tag = soup.find('title')
                if title_tag and title_tag.string:
                    default_title = title_tag.string.strip()
            except:
                pass

        title_input = input(f"Введіть назву курсу [{default_title}]: ").strip()
        args.title = title_input or default_title

    # Вихідний файл
    if not args.output:
        output_dir = os.path.dirname(args.input_file) or '.'
        output_name = os.path.splitext(os.path.basename(args.input_file))[0]
        default_output = os.path.join(output_dir, f"{output_name}_scorm.zip")
        output_input = input(f"Шлях до вихідного файлу [{default_output}]: ").strip()
        args.output = output_input or default_output

    # Версія SCORM
    if args.scorm_version == '2004':  # якщо використовується версія за замовчуванням
        version_input = input("Версія SCORM (1.2 або 2004) [2004]: ").strip()
        if version_input in ['1.2', '2004']:
            args.scorm_version = version_input

    # Опція для HTML
    if file_extension in ['.html', '.htm'] and not args.no_resources:
        resources_input = input("Включати пов'язані ресурси (CSS, зображення тощо)? (y/n) [y]: ").strip().lower()
        args.no_resources = resources_input == 'n'

    print("\nПочинаю конвертацію...")

    # Виклик відповідного конвертера залежно від типу файлу
    if file_extension == '.pdf':
        result = convert_pdf_to_scorm(args.input_file, args.output, args.title, args.scorm_version)
    elif file_extension in ['.docx', '.doc']:
        result = convert_docx_to_scorm(args.input_file, args.output, args.title, args.scorm_version)
    elif file_extension in ['.html', '.htm']:
        result = convert_html_to_scorm(args.input_file, args.output, args.title, args.scorm_version,
                                       not args.no_resources)

    if result:
        print(f"\nУспішно створено SCORM-пакет: {args.output}")
    else:
        print("\nПомилка при створенні SCORM-пакету")
        sys.exit(1)


if __name__ == "__main__":
    main()