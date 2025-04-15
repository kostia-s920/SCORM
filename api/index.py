def handler(request, context):
    """
    Мінімальний обробник Vercel - тільки повертає успішну відповідь
    """
    return {
        "statusCode": 200,
        "body": '{"success":true,"message":"API works!"}',
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
    }