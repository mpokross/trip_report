from typing import Optional, Any


class IMCABaseError(Exception):
    """Base exception for IMCA Report Generator"""
    def __init__(self, message: str, context: Optional[dict] = None):
        """
        Initialize the exception with additional context.

        Args:
            message: Error message
            context: Additional context information about the error
        """
        self.context = context or {}
        super().__init__(message)

    def __str__(self):
        """
        Provide a detailed string representation of the error.
        """
        base_message = super().__str__()
        if self.context:
            context_str = " | ".join(f"{k}: {v}" for k, v in self.context.items())
            return f"{base_message} | Context: {context_str}"
        return base_message


class DataCollectionError(IMCABaseError):
    """Raised when there are issues with data collection"""
    pass


class FileProcessingError(IMCABaseError):
    """Raised when there are issues processing a specific file"""
    pass


class XMLProcessingError(FileProcessingError):
    """Raised when there are issues processing XML files"""
    pass


class DirectoryStructureError(DataCollectionError):
    """Raised when the directory structure is invalid or unexpected"""
    pass


def validate_input(
    value: Any, 
    expected_type: type, 
    name: str, 
    additional_checks: Optional[callable] = None
) -> Any:
    """
    Validate input with type checking and optional additional validation.

    Args:
        value: Input value to validate
        expected_type: Expected type of the input
        name: Name of the input for error messaging
        additional_checks: Optional callable for additional validation

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(value, expected_type):
        raise ValueError(
            f"Invalid type for {name}. "
            f"Expected {expected_type.__name__}, got {type(value).__name__}"
        )

    if additional_checks:
        try:
            result = additional_checks(value)
            if result is False:
                raise ValueError(f"Additional validation failed for {name}")
        except Exception as e:
            raise ValueError(f"Validation error for {name}: {str(e)}")

    return value