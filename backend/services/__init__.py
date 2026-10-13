"""Local intelligence services. Legacy database integration is loaded only on demand."""

def __getattr__(name):
    if name == 'repository_service':
        from .repository_service import repository_service
        return repository_service
    raise AttributeError(name)
