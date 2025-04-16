import streamlit as st
import os
import tempfile
import time
import base64
import shutil
import zipfile
import subprocess
from pathlib import Path
import sys

# Налаштування сторінки
st.set_page_config(
    page_title="SCORM конвертер",
    page_icon="📚",
    layout="wide"
)


# Функція для створення посилання на завантаження
def get_binary_file_downloader_html(bin_file, file_label='Файл'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{os.path.basename(bin_file)}" class="download-link">{file_label}</a>'
    return href


# Перевірка наявності необхідних скриптів
def check_scripts():
    scripts = {
        "pdf_converter.py": "скрипту конвертації PDF",
        "html_converter.py": "скрипту конвертації HTML",
    }

    missing_scripts = []
    for script, description in scripts.items():
        if not os.path.exists(script):
            missing_scripts.append(f"{description} ({script})")

    if missing_scripts:
        st.error(f"Відсутні важливі файли: {', '.join(missing_scripts)}")
        st.info("Завантажте відсутні файли в одну директорію з app.py")
        return False
    return True


# Перевірка залежностей
def check_dependencies():
    try:
        import fitz  # PyMuPDF
        from bs4 import BeautifulSoup
        return True
    except ImportError as e:
        st.error(f"Не вдалося імпортувати необхідні бібліотеки: {str(e)}")
        st.info("Встановіть залежності за допомогою: pip install -r requirements.txt")
        return False


# Конвертуємо PDF в SCORM через підпроцес
def convert_pdf_to_scorm_subprocess(input_path, output_path, title=None, scorm_version="2004", extract_images=True):
    cmd = [sys.executable, "pdf_converter.py", input_path, "--output", output_path]

    if title:
        cmd.extend(["--title", title])

    cmd.extend(["--scorm-version", scorm_version])

    if not extract_images:
        cmd.append("--no-images")

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            st.error(f"Помилка при виконанні pdf_converter.py: {stderr}")
            return False

        return os.path.exists(output_path)
    except Exception as e:
        st.error(f"Помилка при запуску підпроцесу: {str(e)}")
        return False


# Конвертуємо HTML в SCORM через підпроцес
def convert_html_to_scorm_subprocess(input_path, output_path, title=None, scorm_version="2004", include_resources=True):
    cmd = [sys.executable, "html_converter.py", input_path, "--output", output_path]

    if title:
        cmd.extend(["--title", title])

    cmd.extend(["--scorm-version", scorm_version])

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            st.error(f"Помилка при виконанні html_converter.py: {stderr}")
            return False

        return os.path.exists(output_path)
    except Exception as e:
        st.error(f"Помилка при запуску підпроцесу: {str(e)}")
        return False


# Головний інтерфейс
def main():
    # Заголовок і опис
    st.title("SCORM конвертер")
    st.markdown("""
    Цей інструмент дозволяє конвертувати PDF і HTML файли в SCORM-пакети для використання в LMS.
    """)

    # Вибір типу конвертації
    conversion_type = st.radio(
        "Виберіть тип конвертації:",
        ("PDF в SCORM", "HTML в SCORM")
    )

    # Налаштування конвертації
    with st.expander("Налаштування SCORM", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            scorm_version = st.selectbox(
                "Версія SCORM:",
                ("2004", "1.2"),
                index=0
            )
        with col2:
            title = st.text_input("Назва курсу (опціонально):", "")

        if conversion_type == "PDF в SCORM":
            extract_images = st.checkbox("Видобувати зображення з PDF", value=True)
        else:
            include_resources = st.checkbox("Включати зовнішні ресурси", value=True)

    # Функція для завантаження файлу
    uploaded_file = st.file_uploader(
        f"Завантажте {'PDF' if conversion_type == 'PDF в SCORM' else 'HTML'} файл",
        type=['pdf'] if conversion_type == "PDF в SCORM" else ['html', 'htm']
    )

    if uploaded_file is not None:
        # Створюємо тимчасову директорію для роботи з файлами
        with tempfile.TemporaryDirectory() as temp_dir:
            # Шлях до завантаженого файлу
            file_path = os.path.join(temp_dir, uploaded_file.name)

            # Зберігаємо завантажений файл
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            st.success(f"Файл успішно завантажено: {uploaded_file.name}")

            # Шлях до вихідного SCORM-пакету
            output_filename = f"{os.path.splitext(uploaded_file.name)[0]}_scorm.zip"
            output_path = os.path.join(temp_dir, output_filename)

            # Кнопка для запуску конвертації
            if st.button("Конвертувати в SCORM"):
                # Перевіряємо наявність скриптів
                if not check_scripts():
                    return

                # Перевіряємо залежності
                if not check_dependencies():
                    return

                # Показуємо прогрес-бар
                progress_bar = st.progress(0)
                status_text = st.empty()

                status_text.text("Початок конвертації...")
                progress_bar.progress(10)

                try:
                    # Виконуємо конвертацію залежно від типу
                    if conversion_type == "PDF в SCORM":
                        status_text.text("Конвертація PDF в SCORM...")
                        progress_bar.progress(30)

                        # Викликаємо функцію конвертації PDF в SCORM через підпроцес
                        result = convert_pdf_to_scorm_subprocess(
                            file_path,
                            output_path,
                            title,
                            scorm_version,
                            extract_images
                        )

                        progress_bar.progress(90)

                    else:  # HTML в SCORM
                        status_text.text("Конвертація HTML в SCORM...")
                        progress_bar.progress(30)

                        # Викликаємо функцію конвертації HTML в SCORM через підпроцес
                        result = convert_html_to_scorm_subprocess(
                            file_path,
                            output_path,
                            title,
                            scorm_version,
                            include_resources
                        )

                        progress_bar.progress(90)

                    # Перевіряємо результат конвертації
                    if result and os.path.exists(output_path):
                        progress_bar.progress(100)
                        status_text.text("Конвертація успішно завершена!")

                        # Копіюємо результат у тимчасовий файл у поточну директорію
                        temp_output = os.path.join(os.getcwd(), "temp_" + output_filename)
                        shutil.copy2(output_path, temp_output)

                        # Створюємо посилання для завантаження результату
                        st.markdown(
                            get_binary_file_downloader_html(temp_output,
                                                            f"Завантажити SCORM-пакет ({output_filename})"),
                            unsafe_allow_html=True
                        )

                        # Додаткова інформація
                        st.info(f"""
                        📚 **SCORM-пакет створено!**

                        Деталі:
                        - Назва: {title if title else os.path.splitext(uploaded_file.name)[0]}
                        - Версія SCORM: {scorm_version}
                        - Розмір файлу: {round(os.path.getsize(output_path) / (1024 * 1024), 2)} МБ

                        Тепер ви можете завантажити SCORM-пакет і імпортувати його в свою LMS.
                        """)

                    else:
                        progress_bar.progress(100)
                        st.error("Помилка під час конвертації. Перевірте вхідний файл і спробуйте знову.")

                except Exception as e:
                    progress_bar.progress(100)
                    st.error(f"Сталася помилка: {str(e)}")
                    st.exception(e)

    # Додаткова інформація та інструкції
    st.markdown("---")
    st.markdown("""
    ### Як використовувати SCORM конвертер:

    1. **Підготовка**:
       - Переконайтеся, що в директорії з додатком знаходяться файли `pdf_converter.py` та `html_converter.py`
       - Встановіть всі залежності з `requirements.txt`

    2. **Конвертація PDF**:
       - Завантажте PDF файл
       - Вкажіть назву курсу (опціонально)
       - Налаштуйте версію SCORM та інші параметри
       - Натисніть "Конвертувати в SCORM"

    3. **Конвертація HTML**:
       - Завантажте HTML файл
       - Вкажіть назву курсу (опціонально) 
       - Налаштуйте версію SCORM та включення ресурсів
       - Натисніть "Конвертувати в SCORM"

    4. **Імпорт в LMS**:
       - Завантажте створений SCORM-пакет
       - Імпортуйте його у вашу LMS (Moodle, Canvas, Blackboard тощо)
    """)

    # Стилі для покращення інтерфейсу
    st.markdown("""
    <style>
        .download-link {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 10px 2px;
            cursor: pointer;
            border-radius: 5px;
        }
        .download-link:hover {
            background-color: #45a049;
        }
    </style>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()