from .models import RelayRequest, RelayResult

__all__ = ["RelayRequest", "RelayResult", "RelayService"]


def __getattr__(name: str):
    # Avoid importing RelayService while ResourcePlanner imports the JSON
    # repository.  Public ``from zyrelay.relay import RelayService`` remains
    # unchanged.
    if name == "RelayService":
        from .service import RelayService

        return RelayService
    raise AttributeError(name)
