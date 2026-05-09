"""Domain exception types shared across service, guards, and exception handlers."""


class NotFoundError(Exception):
    pass


class OwnershipError(Exception):
    pass
