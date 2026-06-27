@pending
Feature: FR-7 Delegation pipeline
  Scenario: Pending -- delegate asks with local fast path and cache
    Given a command that can be decided by local-fast
    When I run `policyctl intercept --harness forge --domain devops --action write --command "echo hi" --ask-mode delegate`
    Then delegate result should be deterministic and include decision/confidence