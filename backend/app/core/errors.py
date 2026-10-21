class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        self.status_code, self.code, self.message, self.details = status_code, code, message, details
        super().__init__(message)


def unauthenticated() -> AppError:
    return AppError(401, "not_authenticated", "Authentication required.")


def forbidden() -> AppError:
    return AppError(403, "forbidden", "You do not have permission to perform this action.")
