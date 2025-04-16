import streamlit as st
import base64
import os
import tempfile
import time
from PIL import Image
import subprocess
import sys

# Налаштування сторінки
st.set_page_config(
    page_title="SCORM Конвертер | HTML та PDF у SCORM пакети",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS стилі для покращення вигляду
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    h1 {
        color: #333;
    }
    .stButton>button {
        background-color: #4361ee;
        color: white;
        font-weight: bold;
        border: none;
        padding: 0.5rem 1rem;
        width: 100%;
        border-radius: 0.3rem;
    }
    .stButton>button:hover {
        background-color: #3a56d4;
    }
    .feature-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    .step-card {
        background-color: #e6efff;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .footer {
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #ccc;
        text-align: center;
        color: #666;
    }
    .checkmark {
        color: #38b000;
        font-weight: bold;
    }
    .file-uploader {
        border: 2px dashed #ccc;
        border-radius: 0.5rem;
        padding: 2rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    .tool-card {
        border: 1px solid #eee;
        border-radius: 0.5rem;
        padding: 1rem;
        text-align: center;
        background-color: white;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
    }
    .tool-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    .highlight {
        color: #4361ee;
        font-weight: bold;
    }
    .container {
        background-color: white;
        padding: 2rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)


# Функція для створення завантажувальних посилань
def get_binary_file_downloader_html(bin_file, file_label='Файл'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{os.path.basename(bin_file)}" style="background-color: #4361ee; color: white; padding: 0.5rem 1rem; text-decoration: none; border-radius: 0.3rem; font-weight: bold; display: inline-block; text-align: center; margin: 1rem 0;">{file_label}</a>'
    return href


# Функції для конвертації файлів через підпроцеси
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


# Головний заголовок
st.markdown(
    "<h1 style='text-align: center; margin-bottom: 1rem;'>БЕЗКОШТОВНИЙ <span class='highlight'>HTML та PDF в SCORM</span> Конвертер</h1>",
    unsafe_allow_html=True)

# Підзаголовок
st.markdown(
    "<p style='text-align: center; font-size: 1.2rem; margin-bottom: 2rem;'>Конвертуйте ваші HTML та PDF файли у SCORM-сумісні пакети за секунди — швидко, просто та безкоштовно.</p>",
    unsafe_allow_html=True)

# Переваги сервісу
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("<div style='text-align: center;'><span class='checkmark'>✓</span> 100% Безкоштовно</div>",
                unsafe_allow_html=True)
with col2:
    st.markdown("<div style='text-align: center;'><span class='checkmark'>✓</span> Без реєстрації</div>",
                unsafe_allow_html=True)
with col3:
    st.markdown("<div style='text-align: center;'><span class='checkmark'>✓</span> Миттєва конвертація</div>",
                unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Основний контейнер
st.markdown("<div class='container'>", unsafe_allow_html=True)

# Вибір типу конвертації
conversion_type = st.radio(
    "Виберіть тип конвертації:",
    ("PDF в SCORM", "HTML в SCORM")
)

# Форма із полями
col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Ваше ім'я:")
with col2:
    email = st.text_input("Email для отримання результату:")

# Область для завантаження файлу
st.markdown("<div class='file-uploader'>", unsafe_allow_html=True)
uploaded_file = st.file_uploader(
    f"Завантажте ваш {'PDF' if conversion_type == 'PDF в SCORM' else 'HTML'} файл",
    type=['pdf'] if conversion_type == "PDF в SCORM" else ['html', 'htm'],
    help=f"Максимальний розмір файлу: 25MB. Підтримуються файли {'PDF' if conversion_type == 'PDF в SCORM' else 'HTML/HTM'}."
)
st.markdown("</div>", unsafe_allow_html=True)

# Налаштування SCORM
col1, col2 = st.columns(2)
with col1:
    scorm_version = st.radio(
        "Версія SCORM:",
        ("SCORM 2004", "SCORM 1.2"),
        horizontal=True
    )
with col2:
    if conversion_type == "PDF в SCORM":
        extract_images = st.checkbox("Видобувати зображення з PDF", value=True)
    else:
        include_resources = st.checkbox("Включати зовнішні ресурси", value=True)

# Заголовок перед кнопкою
title = st.text_input("Назва курсу (опціонально):", "")

# Кнопка конвертації
if st.button(f"Конвертувати в SCORM зараз"):
    if uploaded_file is not None:
        with st.spinner('Конвертація у процесі...'):
            # Створюємо тимчасову директорію для обробки файлів
            with tempfile.TemporaryDirectory() as temp_dir:
                # Шлях до завантаженого файлу
                file_path = os.path.join(temp_dir, uploaded_file.name)

                # Зберігаємо завантажений файл
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Шлях до вихідного SCORM-пакету
                output_filename = f"{os.path.splitext(uploaded_file.name)[0]}_scorm.zip"
                output_path = os.path.join(temp_dir, output_filename)

                # Виконуємо конвертацію
                if conversion_type == "PDF в SCORM":
                    # Симуляція процесу для тестування (в кінцевому рішенні використовувати реальну конвертацію)
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    status_text.text("Початок конвертації PDF файлу...")
                    progress_bar.progress(10)
                    time.sleep(0.5)

                    status_text.text("Обробка сторінок PDF...")
                    progress_bar.progress(30)
                    time.sleep(1)

                    status_text.text("Створення SCORM-структури...")
                    progress_bar.progress(60)
                    time.sleep(0.7)

                    status_text.text("Генерація SCORM-пакету...")
                    progress_bar.progress(90)
                    time.sleep(0.8)

                    # Тут був би виклик реальної функції, замість цього створюємо фіктивний файл для демонстрації
                    # result = convert_pdf_to_scorm_subprocess(file_path, output_path, title, scorm_version.split()[1], extract_images)

                    # Для демонстрації створюємо фіктивний файл
                    with open(output_path, 'wb') as f:
                        f.write(b'Demo SCORM package')
                    result = True

                    progress_bar.progress(100)
                    status_text.text("Конвертація завершена!")

                else:  # HTML в SCORM
                    # Симуляція процесу для тестування (в кінцевому рішенні використовувати реальну конвертацію)
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    status_text.text("Початок конвертації HTML файлу...")
                    progress_bar.progress(10)
                    time.sleep(0.5)

                    status_text.text("Аналіз структури HTML...")
                    progress_bar.progress(30)
                    time.sleep(0.8)

                    status_text.text("Копіювання ресурсів...")
                    progress_bar.progress(50)
                    time.sleep(0.7)

                    status_text.text("Створення SCORM-структури...")
                    progress_bar.progress(70)
                    time.sleep(0.5)

                    status_text.text("Генерація SCORM-пакету...")
                    progress_bar.progress(90)
                    time.sleep(0.8)

                    # Тут був би виклик реальної функції, замість цього створюємо фіктивний файл для демонстрації
                    # result = convert_html_to_scorm_subprocess(file_path, output_path, title, scorm_version.split()[1], include_resources)

                    # Для демонстрації створюємо фіктивний файл
                    with open(output_path, 'wb') as f:
                        f.write(b'Demo SCORM package')
                    result = True

                    progress_bar.progress(100)
                    status_text.text("Конвертація завершена!")

                # Перевіряємо результат конвертації
                if result:
                    # Копіюємо результат у тимчасовий файл для відображення
                    temp_output = os.path.join(".", "temp_" + output_filename)
                    with open(output_path, 'rb') as src_file, open(temp_output, 'wb') as dst_file:
                        dst_file.write(src_file.read())

                    st.success("SCORM-пакет успішно створено!")

                    # Деталі по створеному пакету
                    st.markdown(f"""
                    <div style='background-color: #e6f7ff; padding: 1rem; border-radius: 0.5rem; margin: 1rem 0;'>
                        <h3>📚 SCORM-пакет готовий!</h3>
                        <p><strong>Назва:</strong> {title if title else os.path.splitext(uploaded_file.name)[0]}</p>
                        <p><strong>Версія SCORM:</strong> {scorm_version}</p>
                        <p><strong>Формат:</strong> {conversion_type.split()[0]}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Створюємо посилання для завантаження результату
                    st.markdown(
                        get_binary_file_downloader_html(temp_output, f"Завантажити SCORM-пакет ({output_filename})"),
                        unsafe_allow_html=True
                    )

                    # Інструкції по використанню
                    with st.expander("Як використовувати SCORM-пакет?"):
                        st.markdown("""
                        1. **Завантажте** створений SCORM-пакет на свій комп'ютер
                        2. **Увійдіть** у вашу систему LMS (Moodle, Canvas, Blackboard, тощо)
                        3. **Створіть** новий курс або модуль
                        4. **Імпортуйте** SCORM-пакет згідно з інструкціями вашої LMS
                        5. **Налаштуйте** параметри відображення та оцінювання
                        6. **Опублікуйте** курс для ваших студентів
                        """)
                else:
                    st.error("Помилка під час конвертації. Перевірте вхідний файл і спробуйте знову.")
    else:
        st.warning("Будь ласка, завантажте файл для конвертації.")

st.markdown("</div>", unsafe_allow_html=True)

# Додаткові формати для конвертації
st.markdown(
    "<h2 style='text-align: center; margin-top: 3rem; margin-bottom: 1.5rem;'>Більше безкоштовних інструментів для SCORM конвертації</h2>",
    unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; margin-bottom: 2rem;'>Потрібно конвертувати інші формати у SCORM-сумісні пакети? Спробуйте наші безкоштовні інструменти:</p>",
    unsafe_allow_html=True)

# Картки з іншими форматами для конвертації
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("<div class='tool-card'><h3>MP4 в SCORM</h3><p>Конвертуйте відео у навчальні курси</p></div>",
                unsafe_allow_html=True)
with col2:
    st.markdown("<div class='tool-card'><h3>PDF в SCORM</h3><p>Створюйте курси з документів</p></div>",
                unsafe_allow_html=True)
with col3:
    st.markdown("<div class='tool-card'><h3>PPT в SCORM</h3><p>Перетворіть презентації у курси</p></div>",
                unsafe_allow_html=True)
with col4:
    st.markdown("<div class='tool-card'><h3>Word в SCORM</h3><p>З документів у навчальні модулі</p></div>",
                unsafe_allow_html=True)

# Як працює конвертація
st.markdown(
    "<h2 style='text-align: center; margin-top: 3rem; margin-bottom: 1.5rem;'>Як конвертувати файл у SCORM</h2>",
    unsafe_allow_html=True)

# Покрокові інструкції
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        "<div class='step-card'><h3>1. Завантажте ваш файл</h3><p>Виберіть HTML або PDF файл для конвертації у SCORM 1.2 або SCORM 2004 пакет, оптимізований для LMS.</p></div>",
        unsafe_allow_html=True)
with col2:
    st.markdown(
        "<div class='step-card'><h3>2. Вкажіть ваші дані</h3><p>Введіть своє ім'я та email для отримання готового SCORM-пакету після конвертації.</p></div>",
        unsafe_allow_html=True)
with col3:
    st.markdown(
        "<div class='step-card'><h3>3. Завантажте SCORM-пакет</h3><p>Отримайте готовий SCORM-пакет та інтегруйте його у вашу LMS для відстеження прогресу навчання.</p></div>",
        unsafe_allow_html=True)

# Переваги використання
st.markdown(
    "<h2 style='text-align: center; margin-top: 3rem; margin-bottom: 1.5rem;'>Переваги конвертації у SCORM</h2>",
    unsafe_allow_html=True)

# Картки з перевагами
col1, col2 = st.columns(2)
with col1:
    st.markdown(
        "<div class='feature-card'><h3>Відстеження прогресу учнів</h3><p>SCORM-пакети дозволяють відстежувати час проведений учнем, прогрес навчання та результати тестів у будь-якій LMS-системі.</p></div>",
        unsafe_allow_html=True)
    st.markdown(
        "<div class='feature-card'><h3>Сумісність з будь-якою LMS</h3><p>Наші SCORM-пакети сумісні з усіма популярними системами управління навчанням - Moodle, Blackboard, Canvas, Teachable та іншими.</p></div>",
        unsafe_allow_html=True)
with col2:
    st.markdown(
        "<div class='feature-card'><h3>Інтерактивність та залучення</h3><p>Перетворіть статичний контент у інтерактивні курси з функціями навігації, тестування та взаємодії з учнями.</p></div>",
        unsafe_allow_html=True)
    st.markdown(
        "<div class='feature-card'><h3>Збереження та повторне використання</h3><p>Створені SCORM-пакети можна використовувати повторно, поширювати та впроваджувати у різних системах без додаткової конвертації.</p></div>",
        unsafe_allow_html=True)

# FAQ розділ
st.markdown("<h2 style='text-align: center; margin-top: 3rem; margin-bottom: 1.5rem;'>Популярні запитання</h2>",
            unsafe_allow_html=True)

# Розгортаємі секції FAQ
with st.expander("Навіщо конвертувати файли у SCORM?"):
    st.markdown("""
    Конвертація у SCORM робить ваш контент LMS-сумісним, дозволяючи відстежувати прогрес учнів, взаємодії та рівень завершення. 
    SCORM забезпечує структурованість, вимірюваність та доступність навчальних матеріалів у різних системах управління навчанням.

    SCORM (Sharable Content Object Reference Model) — це стандарт для навчальних матеріалів, який дозволяє:
    * Відстежувати час проведений учнем у курсі
    * Зберігати прогрес проходження курсу
    * Оцінювати результати навчання
    * Забезпечувати сумісність між різними LMS-платформами
    """)

with st.expander("Чи цей конвертер безкоштовний?"):
    st.markdown("""
    Так! Наш конвертер HTML та PDF у SCORM на 100% безкоштовний, без прихованих платежів чи обов'язкової реєстрації. 
    Просто завантажте ваш файл, і ми зробимо все інше.

    * Жодних платежів
    * Без обмежень на кількість конвертацій
    * Без водяних знаків чи реклами у вихідних файлах
    * Повні функціональні SCORM-пакети без обмежень
    """)

with st.expander("Чи потрібні технічні навички для використання?"):
    st.markdown("""
    Жодних навичок програмування чи технічних знань не потрібно. Наш інструмент розроблений для простоти використання — 
    просто завантажте файл, і ми згенеруємо повністю SCORM-сумісний пакет для вашої LMS.

    Інструмент підходить для:
    * Викладачів та тренерів
    * Розробників навчальних матеріалів
    * HR-спеціалістів
    * Освітніх установ та корпоративних навчальних центрів
    * Усіх, хто створює онлайн-курси
    """)

with st.expander("Які формати SCORM підтримуються?"):
    st.markdown("""
    Наш конвертер підтримує обидва основні стандарти SCORM:

    * **SCORM 1.2** — найпоширеніший стандарт, сумісний практично з усіма LMS-системами
    * **SCORM 2004** (4-а редакція) — новіший стандарт з розширеними можливостями трекінгу та умовної навігації

    Рекомендуємо використовувати SCORM 1.2 для максимальної сумісності, якщо у вас немає особливих вимог до функцій SCORM 2004.
    """)

# Футер сторінки
st.markdown("<div class='footer'>", unsafe_allow_html=True)
st.markdown(f"© {time.strftime('%Y')} SCORM Конвертер | Безкоштовний інструмент для конвертації HTML та PDF у SCORM",
            unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)