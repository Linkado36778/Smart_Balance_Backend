"""Module containing the ReturnModel class, which is used to standardize the return of API endpoints in the application.
This model provides a consistent structure for responses, making it easier to handle and interpret the results of API calls across the application."""

from dataclasses import dataclass
from typing import Any

@dataclass
class ReturnModel:
    """Class to standardize the return of the API endpoints, providing a consistent structure for responses."""

    success: bool
    message: str
    data: Any | None = None

@dataclass
class ReturnException(Exception):
    """Custom exception class to be used for handling errors in the application,

    allowing for standardized error responses.
    """

    message: str
    success: bool
    data: Any | None = None
    status_code: int = 400

    def __post_init__(self):
        # Inicializa a classe base Exception passando a mensagem de erro
        super().__init__(self.message)
