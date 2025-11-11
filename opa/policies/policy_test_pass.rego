package ai.authz_test

import data.ai.authz

test_allow_simple if {
  test_input := {"prompt": "Hello world"}
  d := data.ai.authz.decision
  d.allow == true
  d.action == "allow"
}