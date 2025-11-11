package ai.authz

default allow = false

injection_keywords := {"ignore previous", "bypass", "password", "secret", "ssn"}

# true when any keyword is found (case-insensitive)
contains_injection if {
  input.prompt
  some i
  kw := injection_keywords[i]
  lower_input := lower(input.prompt)
  contains(lower_input, kw)
}

# allow only when prompt exists and no injection keyword found
allow if {
  input.prompt
  not contains_injection
}