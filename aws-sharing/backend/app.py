"""Consent-based, latest-reading-only AURA guardian API for AWS Lambda."""
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
CORS_ORIGINS = {origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin.strip()}
LIVE_TTL_SECONDS = 180
MAX_BODY_BYTES = 32_000


class ApiError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


def response(status, payload, origin=""):
    headers = {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
        "vary": "origin",
    }
    if origin and origin in CORS_ORIGINS:
        headers["access-control-allow-origin"] = origin
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(payload, separators=(",", ":")),
    }


def body_json(event):
    raw = event.get("body") or "{}"
    if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
        raise ApiError(413, "Request is too large.")
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise ApiError(400, "Request body must be valid JSON.")
    if not isinstance(value, dict):
        raise ApiError(400, "Request body must be an object.")
    return value


def claims_for(event):
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        headers = event.get("headers") or {}
        authorization = headers.get("authorization") or headers.get("Authorization") or ""
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise ApiError(401, "Sign in is required.")
        return claims["sub"], token
    except (KeyError, TypeError):
        raise ApiError(401, "Sign in is required.")


def verified_email(access_token):
    endpoint = os.environ["COGNITO_DOMAIN"].rstrip("/") + "/oauth2/userInfo"
    request = urllib.request.Request(endpoint, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(request, timeout=3) as result:
            attributes = json.loads(result.read(16_384))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        raise ApiError(401, "Could not verify the signed-in account. Sign in again.")
    if attributes.get("email_verified") is not True or not attributes.get("email"):
        raise ApiError(403, "Verify your email before creating or joining a circle.")
    return attributes["email"][:254]



def member(circle_id, user_id):
    result = TABLE.get_item(Key={"PK": f"CIRCLE#{circle_id}", "SK": f"MEMBER#{user_id}"})
    return result.get("Item")


def require_member(circle_id, user_id, roles=None):
    found = member(circle_id, user_id)
    if not found or found.get("status") != "active":
        raise ApiError(403, "You are not an approved member of this circle.")
    if roles and found.get("role") not in roles:
        raise ApiError(403, "This action is not available to your circle role.")
    return found


def save_member(circle_id, user_id, email, role, status):
    item = {
        "PK": f"CIRCLE#{circle_id}",
        "SK": f"MEMBER#{user_id}",
        "GSI1PK": f"USER#{user_id}",
        "GSI1SK": f"CIRCLE#{circle_id}",
        "circleId": circle_id,
        "userId": user_id,
        "email": email,
        "role": role,
        "status": status,
        "sharing": False,
        "createdAt": int(time.time()),
    }
    TABLE.put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")


def parse_time(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ApiError(400, "A valid collection timestamp is required.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        raise ApiError(400, "A valid collection timestamp is required.")


def validate_reading(data):
    collected = parse_time(data.get("collectedAt"))
    now_dt = datetime.now(timezone.utc)
    age = (now_dt - collected).total_seconds()
    if age < -30 or age > 120:
        raise ApiError(400, "Reading is too old or its clock is incorrect; send a fresh reading.")
    reading = {"collectedAt": collected.isoformat(timespec="seconds").replace("+00:00", "Z")}
    location = data.get("location")
    if location is not None:
        if not isinstance(location, dict):
            raise ApiError(400, "Location must contain latitude, longitude, and accuracy.")
        try:
            lat, lon = float(location["latitude"]), float(location["longitude"])
            accuracy = float(location.get("accuracy", 0))
        except (KeyError, TypeError, ValueError):
            raise ApiError(400, "Location values are invalid.")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= accuracy <= 100_000):
            raise ApiError(400, "Location values are outside valid bounds.")
        reading["location"] = {"latitude": lat, "longitude": lon, "accuracy": accuracy}
    checks = (("heartRate", 20, 250), ("spo2", 50, 100), ("stepCount", 0, 200_000), ("cadence", 0, 300))
    for name, low, high in checks:
        val = data.get(name)
        if val is None:
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not low <= val <= high:
            raise ApiError(400, f"{name} is outside the accepted range.")
        reading[name] = int(val) if name != "spo2" else round(float(val), 1)
    movement = data.get("movement")
    if movement is not None:
        if movement not in ("still", "walking", "running", "unknown"):
            raise ApiError(400, "movement must be still, walking, running, or unknown.")
        reading["movement"] = movement
    if len(reading) == 1:
        raise ApiError(400, "There is no live sensor or location data to share.")
    return reading


def circle_handlers(method, path, event, user_id, email):
    parts = [p for p in path.split("/") if p]
    if path == "/v1/circles" and method == "POST":
        circle_id = str(uuid.uuid4())
        save_member(circle_id, user_id, email, "patient", "active")
        return 201, {"circleId": circle_id, "role": "patient"}
    if path == "/v1/circles" and method == "GET":
        result = TABLE.query(
            IndexName="UserIndex",
            KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}") & Key("GSI1SK").begins_with("CIRCLE#"),
        )
        return 200, {"circles": [{"circleId": x["circleId"], "role": x["role"], "status": x["status"], "sharing": x.get("sharing", False)} for x in result.get("Items", [])]}

    if len(parts) < 3 or parts[0] != "v1" or parts[1] != "circles":
        return None
    circle_id = parts[2]

    if len(parts) == 4 and parts[3] == "invites" and method == "POST":
        require_member(circle_id, user_id, {"patient"})
        code = secrets.token_urlsafe(24)
        expires = int(time.time()) + 24 * 60 * 60
        digest = hashlib.sha256(code.encode()).hexdigest()
        TABLE.put_item(Item={"PK": f"INVITE#{digest}", "SK": "META", "circleId": circle_id, "createdBy": user_id, "expiresAt": expires})
        return 201, {"inviteCode": code, "expiresAt": expires, "note": "Share this one-time code only with the intended guardian. They must sign in and the patient must approve them."}

    if len(parts) == 3 and parts[2] and method == "GET":
        raise ApiError(404, "Unknown circle endpoint.")

    if len(parts) >= 4 and parts[3] == "members":
        require_member(circle_id, user_id)
        if len(parts) == 4 and method == "GET":
            result = TABLE.query(KeyConditionExpression=Key("PK").eq(f"CIRCLE#{circle_id}") & Key("SK").begins_with("MEMBER#"))
            items = result.get("Items", [])
            own = member(circle_id, user_id)
            if own["role"] != "patient":
                items = [x for x in items if x["userId"] == user_id or (x["role"] == "patient" and x["status"] == "active")]
            return 200, {"members": [{"userId": x["userId"], "email": x.get("email", ""), "role": x["role"], "status": x["status"]} for x in items]}
        if len(parts) == 6 and parts[5] == "approve" and method == "POST":
            require_member(circle_id, user_id, {"patient"})
            other_id = parts[4]
            target = member(circle_id, other_id)
            if not target or target["role"] != "guardian" or target["status"] != "pending":
                raise ApiError(404, "No pending guardian with that account was found.")
            TABLE.update_item(Key={"PK": f"CIRCLE#{circle_id}", "SK": f"MEMBER#{other_id}"}, UpdateExpression="SET #s = :active", ExpressionAttributeNames={"#s": "status"}, ExpressionAttributeValues={":active": "active"})
            return 200, {"approved": True, "email": target.get("email", "")}
        if len(parts) == 5 and method == "DELETE":
            require_member(circle_id, user_id, {"patient"})
            other_id = parts[4]
            target = member(circle_id, other_id)
            if not target or target["role"] != "guardian":
                raise ApiError(404, "Guardian account was not found.")
            TABLE.delete_item(Key={"PK": f"CIRCLE#{circle_id}", "SK": f"MEMBER#{other_id}"})
            return 200, {"removed": True}

    if len(parts) == 4 and parts[3] == "sharing" and method in {"POST", "DELETE"}:
        patient = require_member(circle_id, user_id, {"patient"})
        if method == "DELETE":
            TABLE.update_item(Key={"PK": f"CIRCLE#{circle_id}", "SK": f"MEMBER#{user_id}"}, UpdateExpression="SET sharing = :off REMOVE sharedFields, consentAt", ExpressionAttributeValues={":off": False})
            TABLE.delete_item(Key={"PK": f"CIRCLE#{circle_id}", "SK": f"LATEST#{user_id}"})
            return 200, {"sharing": False, "deletedLatestReading": True}
        body = body_json(event)
        allowed_fields = {"location", "heartRate", "spo2", "stepCount", "cadence", "movement"}
        fields = body.get("fields")
        if body.get("consent") is not True or not isinstance(fields, list) or not fields or not set(fields).issubset(allowed_fields):
            raise ApiError(400, "Explicit consent and a valid list of selected data fields are required.")
        result = TABLE.query(KeyConditionExpression=Key("PK").eq(f"CIRCLE#{circle_id}") & Key("SK").begins_with("MEMBER#"))
        if not any(x["role"] == "guardian" and x["status"] == "active" for x in result.get("Items", [])):
            raise ApiError(409, "Approve at least one guardian before sharing data.")
        TABLE.update_item(Key={"PK": f"CIRCLE#{circle_id}", "SK": f"MEMBER#{user_id}"}, UpdateExpression="SET sharing = :on, consentAt = :now, sharedFields = :fields", ExpressionAttributeValues={":on": True, ":now": int(time.time()), ":fields": sorted(set(fields))})
        return 200, {"sharing": True}

    if len(parts) == 4 and parts[3] == "readings" and method == "POST":
        patient = require_member(circle_id, user_id, {"patient"})
        if not patient.get("sharing"):
            raise ApiError(403, "Sharing is off. Turn it on after reviewing the approved guardians.")
        reading = validate_reading(body_json(event))
        allowed = set(patient.get("sharedFields", []))
        if set(reading) - {"collectedAt"} - allowed:
            raise ApiError(403, "This data type was not selected in the patient’s sharing consent.")
        item = {"PK": f"CIRCLE#{circle_id}", "SK": f"LATEST#{user_id}", "patientId": user_id, "collectedAt": reading["collectedAt"], "expiresAt": int(time.time()) + LIVE_TTL_SECONDS, "reading": reading}
        TABLE.put_item(Item=item)
        return 200, {"accepted": True, "collectedAt": reading["collectedAt"]}

    if len(parts) == 4 and parts[3] == "latest" and method == "GET":
        own = require_member(circle_id, user_id)
        if own["role"] == "patient":
            patient_id = user_id
        else:
            patient = next((x for x in TABLE.query(KeyConditionExpression=Key("PK").eq(f"CIRCLE#{circle_id}") & Key("SK").begins_with("MEMBER#")).get("Items", []) if x["role"] == "patient" and x["status"] == "active"), None)
            if not patient:
                raise ApiError(404, "The patient account is not available.")
            patient_id = patient["userId"]
        patient = member(circle_id, patient_id)
        if not patient or not patient.get("sharing"):
            return 200, {"sharing": False, "reading": None}
        result = TABLE.get_item(Key={"PK": f"CIRCLE#{circle_id}", "SK": f"LATEST#{patient_id}"}).get("Item")
        if not result:
            return 200, {"sharing": True, "reading": None}
        stamp = parse_time(result["collectedAt"])
        stale = (datetime.now(timezone.utc) - stamp).total_seconds() > 45
        return 200, {"sharing": True, "stale": stale, "reading": None if stale else result["reading"]}
    return None


def handler(event, _context):
    request_headers = event.get("headers") or {}
    request_origin = request_headers.get("origin") or request_headers.get("Origin") or ""
    try:
        user_id, access_token = claims_for(event)
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        path = event.get("rawPath", "")
        email = verified_email(access_token) if (path == "/v1/circles" and method == "POST") or (path == "/v1/invites/accept" and method == "POST") else ""
        if path == "/v1/invites/accept" and method == "POST":
            body = body_json(event)
            code = body.get("inviteCode", "")
            if not isinstance(code, str) or not 20 <= len(code) <= 100:
                raise ApiError(400, "Invite code is invalid.")
            digest = hashlib.sha256(code.encode()).hexdigest()
            key = {"PK": f"INVITE#{digest}", "SK": "META"}
            invite = TABLE.get_item(Key=key).get("Item")
            if not invite or invite.get("expiresAt", 0) <= int(time.time()) or invite.get("createdBy") == user_id:
                raise ApiError(404, "Invite is expired, already used, or invalid.")
            circle_id = invite["circleId"]
            TABLE.update_item(Key=key, UpdateExpression="SET usedBy = :u, usedAt = :n", ConditionExpression="attribute_not_exists(usedBy) AND expiresAt > :n", ExpressionAttributeValues={":u": user_id, ":n": int(time.time())})
            try:
                save_member(circle_id, user_id, email, "guardian", "pending")
            except TABLE.meta.client.exceptions.ConditionalCheckFailedException:
                raise ApiError(409, "This account already belongs to the circle.")
            return response(202, {"circleId": circle_id, "status": "pending", "message": "The patient must approve this account before any readings are shared."}, request_origin)
        result = circle_handlers(method, path, event, user_id, email)
        if result is None:
            raise ApiError(404, "Endpoint not found.")
        return response(*result, origin=request_origin)
    except ApiError as exc:
        return response(exc.status, {"error": exc.message}, request_origin)
    except Exception:
        # Never log request bodies, tokens, precise locations, or health readings.
        return response(500, {"error": "The secure AURA sharing service could not complete this request."}, request_origin)
