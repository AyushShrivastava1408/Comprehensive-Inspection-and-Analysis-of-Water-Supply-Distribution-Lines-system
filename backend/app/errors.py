from flask import jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(e: ApiError):
        body = {"error": e.message}
        if e.details:
            body["details"] = e.details
        return jsonify(body), e.status

    @app.errorhandler(HTTPException)
    def _http_error(e: HTTPException):
        return jsonify({"error": e.description or e.name}), e.code

    @app.errorhandler(Exception)
    def _unhandled(e: Exception):
        app.logger.exception("Unhandled error")
        return jsonify({"error": "Internal server error"}), 500
