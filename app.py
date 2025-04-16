import streamlit as st
import os
import tempfile
import time
import base64
from pdf_converter import convert_pdf_to_scorm
from html_converter import convert_html_to_scorm

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
        include_resources = st.checkbox("Включати ресурси (CSS, зображення тощо)", value=True)

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

                    # Викликаємо функцію конвертації PDF в SCORM
                    result = convert_pdf_to_scorm(
                        file_path,
                        output_path,
                        title if title else None,
                        scorm_version,
                        extract_images
                    )

                    progress_bar.progress(90)

                else:  # HTML в SCORM
                    status_text.text("Конвертація HTML в SCORM...")
                    progress_bar.progress(30)

                    # Викликаємо функцію конвертації HTML в SCORM
                    result = convert_html_to_scorm(
                        file_path,
                        output_path,
                        title if title else None,
                        scorm_version,
                        include_resources
                    )

                    progress_bar.progress(90)

                # Перевіряємо результат конвертації
                if result:
                    progress_bar.progress(100)
                    status_text.text("Конвертація успішно завершена!")

                    # Створюємо посилання для завантаження результату
                    st.markdown(
                        get_binary_file_downloader_html(output_path, f"Завантажити SCORM-пакет ({output_filename})"),
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

# Додаткова інформація
st.markdown("---")
st.markdown("""
### Про SCORM-конвертер

Цей інструмент дозволяє швидко конвертувати PDF і HTML файли в SCORM-пакети для використання в системах управління навчанням (LMS).

**Можливості:**
- Конвертація PDF файлів у SCORM з автоматичним розбиттям на сторінки
- Конвертація HTML сторінок у SCORM-пакети з підтримкою зовнішніх ресурсів
- Підтримка SCORM 1.2 і SCORM 2004
- Автоматичне відстеження прогресу проходження
- Налаштування метаданих курсу

**Як це працює:**
1. Завантажте PDF або HTML файл
2. Налаштуйте параметри SCORM-пакету
3. Натисніть кнопку "Конвертувати в SCORM"
4. Завантажте створений SCORM-пакет
5. Імпортуйте пакет в свою LMS (Moodle, Canvas, Blackboard тощо)
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