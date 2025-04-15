import base64
import os
import json
import tempfile

from scripts.html_converter import convert_html_to_scorm
from scripts.pdf_converter import convert_pdf_to_scorm


def handler(request):
    try:
        body = request.get_json()
    except:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON"})
        }

    file_type = body.get('file_type', '').lower()
    file_content_base64 = body.get('file_content', '')
    file_name = body.get('file_name', 'document')
    title = body.get('title', '')
    scorm_version = body.get('scorm_version', '2004')

    try:
        file_content = base64.b64decode(file_content_base64)
    except:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid Base64 file"})
        }

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as temp_file:
        temp_file.write(file_content)
        input_path = temp_file.name

    output_path = os.path.join(tempfile.gettempdir(), f"{file_name}_scorm.zip")

    result = False
    if file_type in ['html', 'htm']:
        result = convert_html_to_scorm(input_path, output_path, title=title, scorm_version=scorm_version)
    elif file_type == 'pdf':
        result = convert_pdf_to_scorm(input_path, output_path, title=title, scorm_version=scorm_version)
    else:
        os.unlink(input_path)
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Unsupported file type: {file_type}"})
        }

    if not result or not os.path.exists(output_path):
        os.unlink(input_path)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "SCORM generation failed"})
        }

    with open(output_path, 'rb') as f:
        scorm_content = f.read()

    scorm_base64 = base64.b64encode(scorm_content).decode('utf-8')

    os.unlink(input_path)
    os.unlink(output_path)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "success": True,
            "scorm_package": scorm_base64,
            "file_name": f"{file_name}_scorm.zip"
        })
    }