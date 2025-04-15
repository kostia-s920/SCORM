const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

exports.handler = async function(event, context) {
  // Перевірка методу запиту
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: 'Method Not Allowed' })
    };
  }

  try {
    // Розбір multipart/form-data
    // Примітка: у реальному коді тут потрібно використовувати бібліотеку для розбору форми
    // Наприклад, multipart, formidable або busboy
    console.log("Отримано запит на конвертацію HTML");

    // Для спрощення демонстрації, припустимо, що ми отримуємо base64-закодований HTML
    let requestBody;
    try {
      requestBody = JSON.parse(event.body);
    } catch (e) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'Invalid JSON body' })
      };
    }

    // Отримання даних з запиту
    const fileContent = requestBody.fileContent; // Base64 вміст файлу
    const title = requestBody.title || 'SCORM Курс';

    if (!fileContent) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'No file content provided' })
      };
    }

    // Створення тимчасової директорії
    const tempDir = path.join(os.tmpdir(), 'scorm-converter-' + Date.now());
    fs.mkdirSync(tempDir, { recursive: true });
    console.log(`Створено тимчасову директорію: ${tempDir}`);

    // Запис HTML файлу
    const htmlPath = path.join(tempDir, 'input.html');
    fs.writeFileSync(htmlPath, Buffer.from(fileContent, 'base64'));
    console.log(`Збережено HTML файл: ${htmlPath}`);

    // Шлях до вихідного файлу
    const outputPath = path.join(tempDir, 'output.zip');

    // Шлях до Python скрипта
    const scriptPath = path.join(__dirname, 'scripts', 'html_converter.py');
    console.log(`Шлях до скрипта: ${scriptPath}`);

    // Виклик Python скрипта
    return new Promise((resolve, reject) => {
      console.log(`Запуск команди: python ${scriptPath} ${htmlPath} --output ${outputPath} --title "${title}"`);

      execFile('python3', [
        scriptPath,
        htmlPath,
        '--output', outputPath,
        '--title', title
      ], (error, stdout, stderr) => {
        console.log("Скрипт виконано");
        console.log("stdout:", stdout);

        if (error) {
          console.error(`Помилка виконання: ${error}`);
          console.error("stderr:", stderr);

          return resolve({
            statusCode: 500,
            body: JSON.stringify({
              error: 'Execution error',
              details: error.message,
              stdout: stdout,
              stderr: stderr
            })
          });
        }

        // Перевірка, чи створено файл
        if (!fs.existsSync(outputPath)) {
          console.error(`Файл не створено: ${outputPath}`);
          return resolve({
            statusCode: 500,
            body: JSON.stringify({
              error: 'Output file not created',
              stdout: stdout,
              stderr: stderr
            })
          });
        }

        // Читання створеного SCORM пакету
        console.log(`Читання файлу: ${outputPath}`);
        const scormContent = fs.readFileSync(outputPath);
        const base64Content = scormContent.toString('base64');

        // Очищення тимчасових файлів
        try {
          fs.rmdirSync(tempDir, { recursive: true });
          console.log(`Видалено тимчасову директорію: ${tempDir}`);
        } catch (e) {
          console.error(`Помилка очищення: ${e}`);
        }

        // Повернення результату
        resolve({
          statusCode: 200,
          body: JSON.stringify({
            message: "Конвертація успішна",
            filename: `${title.replace(/[^a-zA-Z0-9]/g, '_')}_scorm.zip`,
            content: base64Content
          }),
          headers: {
            'Content-Type': 'application/json'
          }
        });
      });
    });
  } catch (error) {
    console.error(`Загальна помилка: ${error}`);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: error.message })
    };
  }
};