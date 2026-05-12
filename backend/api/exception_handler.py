from rest_framework.views import exception_handler as drf_exception_handler


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    message = detail.get("detail") if isinstance(detail, dict) else None

    response.data = {
        "error": {
            "code": response.status_code,
            "message": str(message or "Request failed."),
            "details": detail,
        }
    }
    return response
