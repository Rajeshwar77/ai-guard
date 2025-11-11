package ai.authz

# Default structured decision
default decision = {"allow": false, "action": "deny", "policy_id": "p_default", "reason": "no input", "score": 0.0}

# Keyword set (lowercase)
injection_keywords := {"ignore previous", "bypass", "password", "secret", "ssn", "credit card", "ccnum"}

# Determines whether input.prompt contains any injection keyword
contains_injection if {
  input.prompt
  some idx
  kw := injection_keywords[idx]
  lower_input := lower(input.prompt)
  contains(lower_input, kw)
}

# Simple scoring (0..1) — presence of keyword sets higher risk
risk_score = 1.0 if {
  contains_injection
}
risk_score = 0.0 if {
  not contains_injection
}

# Return structured decision object for allow
decision = {
  "allow": true,
  "action": "allow",
  "policy_id": "p_allow_001",
  "reason": "ok",
  "score": risk_score
} if {
  input.prompt
  not contains_injection
}

# Return structured decision object for deny (injection)
decision = {
  "allow": false,
  "action": "deny",
  "policy_id": "p_injection_001",
  "reason": "injection_keyword_matched",
  "score": risk_score
} if {
  contains_injection
}
