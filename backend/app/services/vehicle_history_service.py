from typing import Any, Protocol


class VehicleHistoryService(Protocol):
    """Interface for future repair/history aggregation."""

    def get_history(self, vehicle_id: int) -> dict[str, Any]: ...


class StubVehicleHistoryService:
    def get_history(self, vehicle_id: int) -> dict[str, Any]:
        return {"vehicle_id": vehicle_id, "previous_repairs": [], "available": False}
