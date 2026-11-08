"""Stable error taxonomy shared by workers and the HTTP boundary."""


class AppError(Exception):
    status_code = 400
    code = "invalid_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class QueueFull(AppError):
    status_code = 429
    code = "queue_full"


class ModelUnavailable(AppError):
    status_code = 503
    code = "model_unavailable"


class VisionUnavailable(AppError):
    status_code = 422
    code = "vision_unavailable"


class InvalidImage(AppError):
    status_code = 422
    code = "invalid_image"


class UnsupportedFoodInput(AppError):
    status_code = 422
    code = "unsupported_food_input"


class NoFoodDetected(AppError):
    status_code = 422
    code = "no_food_detected"


class CatalogUnavailable(AppError):
    status_code = 503
    code = "catalog_unavailable"


class GenerationCancelled(AppError):
    status_code = 409
    code = "cancelled"


class GenerationTimeout(AppError):
    status_code = 504
    code = "generation_timeout"
