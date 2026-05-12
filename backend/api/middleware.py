import logging

from django.db import OperationalError
from django.http import JsonResponse


logger = logging.getLogger(__name__)


class ApiExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except Exception as exc:
            if not request.path.startswith("/api/"):
                raise

            logger.exception("Unhandled API exception for %s", request.path)

            message = "Internal server error."
            hint = None

            if isinstance(exc, OperationalError):
                message = "Database operation failed."
                if "no column named" in str(exc).lower():
                    hint = "The database schema is out of sync. Run `python manage.py migrate`."

            payload = {
                "error": {
                    "code": "internal_server_error",
                    "message": message,
                    "details": {
                        "exception": exc.__class__.__name__,
                    },
                }
            }

            if hint:
                payload["error"]["details"]["hint"] = hint

            return JsonResponse(payload, status=500)

        if request.path.startswith("/api/"):
            content_type = response.get("Content-Type", "")
            if response.status_code >= 400 and "application/json" not in content_type.lower():
                return JsonResponse(
                    {
                        "error": {
                            "code": response.status_code,
                            "message": getattr(response, "reason_phrase", "Request failed."),
                            "details": {},
                        }
                    },
                    status=response.status_code,
                )

        return response
