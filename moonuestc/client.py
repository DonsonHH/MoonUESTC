"""CAS + portal warmup + micro-app entry. No CAPTCHA/MFA automation."""
import base64
import re
import secrets
import time
import urllib.parse
from html.parser import HTMLParser

from .errors import AuthRequired, ToolError

ORIGIN = "https://jzsz.uestc.edu.cn"
CAS = "https://idas.uestc.edu.cn/authserver"
LOGIN = CAS + "/login?service=" + urllib.parse.quote(ORIGIN + "/", safe="")
H5 = ORIGIN + "/daily-checkin-h5/index.html?appId=294"
ENTRY = ORIGIN + "/daily-checkin/checkLogin?appId=294"
HEADERS = {"Platform": "h5", "Origin": ORIGIN, "Referer": H5,
           "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"}
CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"


class LoginInputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input":
            for key in (values.get("name"), values.get("id")):
                if key in ("execution", "pwdEncryptSalt") and values.get("value"):
                    self.values[key] = values["value"]


def login_fields(html):
    parser = LoginInputs()
    parser.feed(html)
    fields = parser.values
    if "pwdEncryptSalt" not in fields:
        match = re.search(r"pwdEncryptSalt[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", html)
        if match:
            fields["pwdEncryptSalt"] = match.group(1)
    if not fields.get("execution") or len(fields.get("pwdEncryptSalt", "").encode()) != 16:
        raise ToolError("login_page_changed", "cas_page")
    return fields


def encrypt_password(password, salt):
    # Protocol compatible with MoonCheck's wsc_cas.py and the CAS encrypt.js.
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    prefix = "".join(secrets.choice(CHARS) for _ in range(64))
    iv = "".join(secrets.choice(CHARS) for _ in range(16)).encode()
    encrypted = AES.new(salt.encode(), AES.MODE_CBC, iv).encrypt(pad((prefix + password).encode(), 16))
    return base64.b64encode(encrypted).decode("ascii")


class School:
    def __init__(self, transport, account, budget, emit=lambda *args: None):
        self.transport, self.account, self.budget, self.emit = transport, account, budget, emit

    def api(self, path, *, stage, payload=None):
        r = self.transport.request("POST" if payload is not None else "GET",
                                   ORIGIN + "/daily-checkin/api" + path,
                                   headers=HEADERS, payload=payload, stage=stage)
        if r.status in (301, 302, 303, 401, 403):
            raise AuthRequired("session_rejected", stage)
        if r.status != 200:
            raise ToolError("http_error", stage, r.status)
        data = r.json(stage)
        if not isinstance(data, dict) or type(data.get("code")) is not int:
            raise ToolError("api_contract_changed", stage)
        if data["code"] == 5000 or (data["code"] == 4001 and re.search(
                r"登录|会话|未认证", str(data.get("msg", "")))):
            raise AuthRequired("session_rejected", stage, data["code"])
        if data["code"] != 0 or data.get("ok") is False:
            raise ToolError("business_error", stage, data["code"])
        return data.get("data")

    def today(self):
        return self.api("/student-checkin-record/today", stage="today")

    def schedule(self):
        return self.api("/checkin-schedule/effective", stage="schedule")

    def locations(self):
        return self.api("/checkin-location/available-locations", stage="locations")

    def reverse_geocode(self, latitude, longitude):
        # Translate supplied coordinates into an address; this does not locate the client.
        query = urllib.parse.urlencode({"lat": latitude, "lng": longitude})
        data = self.api("/map/reverse?" + query, stage="reverse_geocode")
        if isinstance(data, str) and data.strip():
            return data
        if isinstance(data, dict):
            for key in ("address", "reverseGeocode", "formattedAddress"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        raise ToolError("reverse_geocode_unavailable", "reverse_geocode")

    def submit(self, payload):
        return self.api("/student-checkin-record/checkin", stage="checkin_post", payload=payload)

    def enter(self):
        r = self.transport.request("GET", ORIGIN + "/api/isLoginFailure?_t=" + str(int(time.time() * 1000)), stage="portal_warmup",
            headers={"Accept": "application/json, text/plain, */*", "Origin": ORIGIN,
                     "Referer": ORIGIN + "/", "Cache-Control": "no-cache"})
        if r.status in (301, 302, 303, 401, 403):
            raise AuthRequired("portal_session_rejected", "portal_warmup")
        if r.status != 200:
            raise ToolError("portal_warmup_failed", "portal_warmup", r.status)
        self.emit("stage_ok", stage="portal_warmup")
        r = self.transport.follow(ENTRY, stage="micro_app_entry", headers={"Referer": ORIGIN + "/"})
        u = urllib.parse.urlsplit(r.url)
        if (r.status != 200 or u.hostname != "jzsz.uestc.edu.cn"
                or u.path != "/daily-checkin-h5/index.html"
                or urllib.parse.parse_qs(u.query).get("appId") != ["294"]):
            raise AuthRequired("micro_app_unauthorized", "micro_app_entry")
        self.emit("stage_ok", stage="micro_app_entry")
        return self.today()

    def connect(self):
        if self.transport.has_session():
            try:
                data = self.enter()
                self.emit("stage_ok", stage="session_reused")
                return data
            except AuthRequired:
                self.emit("stage_failed", stage="cached_session")
        # Fresh Cookie jar, one credential POST, then require business authorization.
        self.transport.clear()
        self.transport.fingerprint(self.account["browser_fingerprint"])
        r = self.transport.request("GET", ORIGIN + "/", stage="platform_previsit")
        if r.status not in (200, 301, 302, 303):
            raise ToolError("platform_previsit_failed", "platform_previsit", r.status)
        r = self.transport.request("GET", LOGIN, stage="cas_page",
                                   headers={"Accept": "text/html,application/xhtml+xml"})
        if r.status != 200:
            raise ToolError("login_page_http_error", "cas_page", r.status)
        fields = login_fields(r.text)
        self.emit("stage_ok", stage="cas_page")
        self.budget()
        form = {"username": self.account["student_id"],
                "password": encrypt_password(self.account["password"], fields["pwdEncryptSalt"]),
                "execution": fields["execution"], "captcha": "", "_eventId": "submit",
                "cllt": "userNameLogin", "dllt": "generalLogin", "lt": ""}
        r = self.transport.request("POST", LOGIN, stage="cas_submit", form=form,
                                   headers={"Origin": "https://idas.uestc.edu.cn", "Referer": LOGIN})
        loc = r.headers.get("Location", "")
        u = urllib.parse.urlsplit(urllib.parse.urljoin(LOGIN, loc))
        if (r.status in (301, 302, 303) and loc and u.scheme == "https"
                and u.hostname == "jzsz.uestc.edu.cn" and urllib.parse.parse_qs(u.query).get("ticket")):
            self.transport.follow(urllib.parse.urljoin(LOGIN, loc), stage="ticket_exchange")
            if not self.transport.has_session():
                raise ToolError("platform_session_missing", "ticket_exchange")
            self.emit("stage_ok", stage="cas_authenticated")
            try:
                return self.enter()
            except AuthRequired:
                raise ToolError("micro_app_unauthorized_after_login", "micro_app_entry") from None
        if re.search(r"reAuthLoginView|isMultifactor|authLogin", loc) or re.search(
                r"二次验证|多因素认证|isMultifactor\s*[=:]\s*['\"]?true", r.text):
            raise ToolError("need_manual_mfa", "cas_submit")
        if re.search(r"验证码错误|请输入验证码|滑块验证|安全验证", r.text):
            raise ToolError("need_manual_captcha", "cas_submit")
        raise ToolError("login_rejected", "cas_submit", r.status)
