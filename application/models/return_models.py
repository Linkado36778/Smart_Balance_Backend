"""Module containing the ReturnModel class, which is used to standardize the return of API endpoints in the application.
This model provides a consistent structure for responses, making it easier to handle and interpret the results of API calls across the application."""

from datetime import datetime
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

#region Default

@dataclass
class ReturnModel(Generic[T]):
    """Class to standardize the return of the API endpoints, providing a consistent structure for responses."""

    success: bool
    message: str
    data: Optional[T] = None

@dataclass
class ReturnException(Exception, Generic[T]):
    """Custom exception class to be used for handling errors in the application,

    allowing for standardized error responses.
    """

    message: str
    success: bool
    data: Optional[T] = None
    status_code: int = 400

    def __post_init__(self):
        # Inicializa a classe base Exception passando a mensagem de erro
        super().__init__(self.message)

#region User

@dataclass
class ReturnSuccessUserModel():
    """Class to standardize the return of user-related API endpoints, providing a consistent structure for responses."""

    id: int
    email: str
    birthdate: datetime
    weight_kg: float
    height_m: float
    sex: str
    created_at: datetime
