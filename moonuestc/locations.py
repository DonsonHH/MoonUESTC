"""Named presets and custom named locations; no network calls or live positioning."""
import copy
from .coordinates import finite_number, normalize_coordinate_system, to_gcj02
from .errors import ToolError

DEFAULT_PRESET_ID = "xuezhi_group3"
PRESETS = {
    DEFAULT_PRESET_ID: {
        "name": "学知三组团", "latitude": 30.757413, "longitude": 103.930739,
        "coordinate_system": "wgs84",
        "reverse_geocode": "中国四川省成都市郫都区合作街道银杏大道",
        # Screenshot accuracy; retained as static historical metadata, not a new measurement.
        "request_metadata": {"accuracy": 40},
    },
}
FIXED_LOCATION_KEYS = {"mode", "name", "latitude", "longitude", "reverse_geocode",
                       "coordinate_system", "request_metadata"}
PRESET_LOCATION_KEYS = {"mode", "preset", "reverse_geocode", "request_metadata"}


def _name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80:
        raise ToolError("invalid_location_name", "location")
    return value.strip()


def get_preset(value):
    if not isinstance(value, str):
        raise ToolError("unknown_location_preset", "location")
    for key, preset in PRESETS.items():
        if value in (key, preset["name"]):
            return key, copy.deepcopy(preset)
    raise ToolError("unknown_location_preset", "location")


def resolve_location(account):
    raw, legacy = account.get("location"), account.get("checkin_payload")
    if raw is None:
        return None
    if legacy is not None:
        raise ToolError("ambiguous_location_configuration", "location")
    if not isinstance(raw, dict):
        raise ToolError("invalid_fixed_location_configuration", "location")
    mode = raw.get("mode")
    if mode == "fixed":
        if not set(raw) <= FIXED_LOCATION_KEYS:
            raise ToolError("invalid_fixed_location_configuration", "location")
        result = copy.deepcopy(raw)
        result["name"] = _name(raw.get("name", "自定义位置"))
        return result
    if mode == "preset":
        if not set(raw) <= PRESET_LOCATION_KEYS:
            raise ToolError("invalid_preset_location_configuration", "location")
        preset_id, result = get_preset(raw.get("preset"))
        result.update(mode="fixed", _preset_id=preset_id)
        if "reverse_geocode" in raw:
            result["reverse_geocode"] = raw["reverse_geocode"]
        metadata = raw.get("request_metadata", {})
        if not isinstance(metadata, dict):
            raise ToolError("invalid_request_metadata", "location")
        result["request_metadata"] = {**result.get("request_metadata", {}), **metadata}
        return result
    raise ToolError("unsupported_location_mode", "location")


def location_details(account):
    location = resolve_location(account)
    if location is None:
        legacy = account.get("checkin_payload")
        return {"locationName": "旧版固定坐标" if legacy is not None else None,
                "inputCoordinateSystem": "gcj02" if legacy is not None else None,
                "outputCoordinateSystem": "gcj02", "coordinateConversion": "none"}
    system = normalize_coordinate_system(location.get("coordinate_system", "gcj02"))
    details = {"locationName": location["name"], "inputCoordinateSystem": system,
               "outputCoordinateSystem": "gcj02",
               "coordinateConversion": "wgs84_to_gcj02_approx" if system == "wgs84" else "none"}
    if all(finite_number(location.get(key)) for key in ("latitude", "longitude")):
        try:
            _, _, details["coordinateConversion"] = to_gcj02(location["latitude"], location["longitude"], system)
        except ToolError:
            pass
    if "_preset_id" in location:
        details["presetId"] = location["_preset_id"]
    return details


def list_presets():
    items = []
    for preset_id, value in PRESETS.items():
        value = copy.deepcopy(value)
        latitude, longitude, method = to_gcj02(value["latitude"], value["longitude"], value["coordinate_system"])
        items.append({"id": preset_id, "name": value["name"],
                      "source": {"latitude": value["latitude"], "longitude": value["longitude"],
                                 "coordinateSystem": value["coordinate_system"]},
                      "submittedCoordinates": {"latitude": latitude, "longitude": longitude, "coordinateSystem": "gcj02"},
                      "coordinateConversion": method, "address": value["reverse_geocode"],
                      "config": {"mode": "preset", "preset": preset_id}})
    return items
