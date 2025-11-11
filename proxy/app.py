
from fastapi import FastAPI, Request, HTTPException, Response
from pydantic import BaseModel
import re, time, json, os, requests

app = FastAPI()
AUDIT_FILE = 'audit.log'
TENANT_HEADER = 'x-tenant-id'
MODEL_URL = os.environ.get('MODEL_URL', 'http://model:5000/generate')
OPA_DECISION_URL = os.environ.get("OPA_DECISION_URL", "http://opa:8181/v1/data/ai/authz/decision")


# Simple DLP regexes
PII_PATTERNS = [
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '<SSN>'),
    (re.compile(r'\b\d{12}\b'), '<ID>'),
    (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '<EMAIL>'),
]

INJECTION_KEYWORDS = ['ignore previous', 'bypass', 'password', 'secret', 'ssn']

class Prompt(BaseModel):
    prompt: str

def redact(text):
    out = text
    for pat, repl in PII_PATTERNS:
        out = pat.sub(repl, out)
    return out

def detect_injection_text(text):
    p = text.lower()
    for kw in INJECTION_KEYWORDS:
        if kw in p:
            return True, kw
    return False, None

def write_audit(entry):
    with open(AUDIT_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')

@app.post('/authorize')
async def authorize(request: Request):
    """
    Called by Envoy ext_authz (HTTP or gRPC adapter). Expects JSON body with {"prompt": "..."} or full request.
    Returns a JSON object with allow boolean. If using HTTP ext_authz, Envoy expects HTTP 200 with body.
    If using gRPC ext_authz, Envoy expects a CheckResponse; but many setups adapt HTTP responses.
    """
    body = await request.json() if request.headers.get("content-type","").startswith("application/json") else {}
    tenant = request.headers.get(TENANT_HEADER) or body.get("tenant") or "unknown"

    opa_input = {"tenant": tenant, "prompt": body.get("prompt")}
    try:
        r = requests.post(OPA_DECISION_URL, json={"input": opa_input}, timeout=5)
    except Exception as e:
        raise HTTPException(status_code=502, detail="OPA error: %s" % str(e))
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="OPA returned non-200")

    result = r.json().get("result") or {}
    # expected fields: allow (bool), action (deny/mask/allow), policy_id, reason, score
    allow = bool(result.get("allow", False))
    action = result.get("action", "deny")
    # Build an ext_authz compatible response for Envoy HTTP ext_authz filter.
    # Envoy expects a 200 with an empty body and ok status for allow; for deny return 403.
    if allow:
        # Optionally set headers Envoy will forward to upstream
        # We return a 200 and include a header x-auth-decision with encoded details so Envoy can forward upstream.
        response = {
            "allow": True,
            "policy_id": result.get("policy_id"),
            "reason": result.get("reason"),
            "action": action,
            "score": result.get("score", 0.0)
        }
        return response
    else:
        # Deny result — respond with HTTP 403 and details to help auditing
        raise HTTPException(status_code=403, detail=json.dumps({
            "allow": False,
            "policy_id": result.get("policy_id"),
            "reason": result.get("reason"),
            "action": action,
            "score": result.get("score", 0.0)
        }))

@app.post('/proxy')
async def proxy(prompt: Prompt, request: Request):
    tenant = request.headers.get(TENANT_HEADER)
    if not tenant:
        raise HTTPException(status_code=400, detail="Missing tenant header 'x-tenant-id'")

    # Input sanitization / injection detection (double-check)
    injection, reason = detect_injection_text(prompt.prompt)
    timestamp = int(time.time())
    audit_entry = {
        'tenant_id': tenant,
        'timestamp': timestamp,
        'prompt': prompt.prompt,
        'injection_detected': injection,
        'injection_reason': reason,
        'decision': None,
        'response': None
    }

    if injection:
        audit_entry['decision'] = 'deny'
        write_audit(audit_entry)
        raise HTTPException(status_code=403, detail=f'Prompt rejected (injection keyword: {reason})')

    # Forward to model
    resp = requests.post(MODEL_URL, json={'prompt': prompt.prompt}, timeout=10)
    if resp.status_code != 200:
        audit_entry['decision'] = 'error'
        write_audit(audit_entry)
        raise HTTPException(status_code=502, detail='Downstream model error')

    model_output = resp.json().get('output', '')
    # DLP redaction on model output
    redacted = redact(model_output)
    audit_entry['decision'] = 'allow'
    audit_entry['response'] = redacted
    write_audit(audit_entry)

    return {'response': redacted}
