"""Single-account flow; an uncertain check-in POST is never resent."""
import hashlib
import time
from pathlib import Path

from .client import School
from .locations import location_details
from .errors import ToolError
from .policy import TERMINAL, build_payload, check_fence, location_configured, location_source, now, valid_today, verified, window
from .transport import Transport


def account_key(account):
    return hashlib.sha256(account["student_id"].encode()).hexdigest()[:32]


def cookie_path(directory, account):
    binding = "\0".join(account[k] for k in ("student_id", "browser_fingerprint", "password"))
    name = hashlib.sha256(binding.encode()).hexdigest()[:32]
    return Path(directory) / "cookies" / (name + ".lwp")


def reconcile(school, state, key, day, clock, sleep):
    last_reason = "record_not_confirmed"
    for attempt in range(3):
        if attempt:
            sleep(2)
        try:
            instant = clock()
            if instant.date().isoformat() != day:
                raise ToolError("business_date_changed", "verification")
            data = school.today()
            if verified(data, instant):
                state.outcome(key, day, "confirmed")
                return {"result": "confirmed", "businessDate": day, "status": "CHECKED_IN", "abnormalFlag": False}
            status = valid_today(data, instant)
            if status in TERMINAL:
                return {"result": "record_changed", "businessDate": day, "status": status}
        except ToolError as error:
            last_reason = error.reason
            if error.reason in ("abnormal_record", "business_date_mismatch", "business_date_changed"):
                break
    state.outcome(key, day, "unknown")
    return {"result": "submission_unknown", "businessDate": day, "reason": last_reason}


def run_account(account, mode, state, directory, *, clock=now, sleep=time.sleep,
                emit=lambda *args, **kwargs: None, transport_factory=Transport):
    key = account_key(account)
    transport = transport_factory(account["user_agent"], cookie_path(directory, account))
    school = School(transport, account,
                    budget=lambda: state.login_budget(key, clock().date().isoformat()), emit=emit)
    try:
        data = school.connect()
        instant = clock()
        day = instant.date().isoformat()
        status = valid_today(data, instant)
        emit("record_read", businessDate=day, status=status, abnormalFlag=data.get("abnormalFlag"))
        if mode == "diagnose":
            win = window(school.schedule(), clock())
            locs = school.locations()
            if not isinstance(locs, list) or not locs:
                raise ToolError("locations_unavailable", "locations")
            return {"result": "auth_ready", "businessDate": day, "status": status,
                    "checkinWindow": win, "locationCount": len(locs),
                    "payloadConfigured": location_configured(account),
                    "locationConfigured": location_configured(account), "locationSource": location_source(account),
                    **location_details(account)}
        if status in TERMINAL and mode != "prepare":
            if status == "CHECKED_IN" and state.claimed(key, day) and verified(data, instant):
                state.outcome(key, day, "confirmed")
                return {"result": "confirmed", "businessDate": day, "status": status, "abnormalFlag": False}
            return {"result": "already_recorded", "businessDate": day, "status": status}
        if state.claimed(key, day) and mode != "prepare":
            return reconcile(school, state, key, day, clock, sleep)
        payload = build_payload(account, instant)
        check_fence(payload, school.locations())
        address = payload["reverseGeocode"]
        if not address:
            address = school.reverse_geocode(payload["latitude"], payload["longitude"])
        payload["reverseGeocode"] = address
        win = window(school.schedule(), clock())
        if mode == "prepare":
            return {"result": "dry_run_ready", "businessDate": day, "checkinWindow": win,
                    "submitted": False, "alreadyRecorded": status in TERMINAL, "locationSource": location_source(account), **location_details(account)}
        if mode != "checkin":
            raise ToolError("invalid_mode", "local")
        if not win["open"]:
            raise ToolError("outside_checkin_window", "schedule")
        # Refresh status and schedule just before the durable claim.
        fresh = school.today()
        instant = clock()
        if instant.date().isoformat() != day:
            raise ToolError("business_date_changed", "today")
        status = valid_today(fresh, instant)
        if status in TERMINAL:
            return {"result": "already_recorded", "businessDate": day, "status": status}
        if not window(school.schedule(), clock())["open"]:
            raise ToolError("outside_checkin_window", "schedule")
        instant = clock()
        if instant.date().isoformat() != day:
            raise ToolError("business_date_changed", "checkin_post")
        payload = build_payload(account, instant)
        payload["reverseGeocode"] = address
        if not state.claim(key, day):
            return reconcile(school, state, key, day, clock, sleep)
        emit("post_claim_saved", businessDate=day)
        try:
            school.submit(payload)
        except ToolError as error:
            # Even an HTTP/network error may follow an accepted server-side write.
            emit("post_response_uncertain", reason=error.reason, stage=error.stage)
        return reconcile(school, state, key, day, clock, sleep)
    finally:
        transport.save()
