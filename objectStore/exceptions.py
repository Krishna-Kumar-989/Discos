class ObjectStoreError(Exception):
    """Base exception for all Object Store errors."""
    pass

class ObjectStoreConfigurationError(ObjectStoreError):
    """Raised when the object store is misconfigured or a provider is unsupported."""
    pass

class ObjectNotFoundError(ObjectStoreError):
    """Raised when the requested object is not found in the bucket."""
    pass

class BucketNotFoundError(ObjectStoreError):
    """Raised when the requested bucket does not exist."""
    pass

class BucketOperationError(ObjectStoreError):
    """Raised when an operation on a bucket (like creation or deletion) fails."""
    pass

class ObjectOperationError(ObjectStoreError):
    """Raised when an operation on an object (like upload or download) fails."""
    pass
