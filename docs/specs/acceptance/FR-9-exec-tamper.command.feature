@pending
Feature: FR-9 Exec TOCTOU protection
  Scenario: Pending -- deny when policy hash changes before execution
    Given a command that is initially allowed
    And policy files change after pre-exec policy resolution
    When I run `policyctl exec --harness forge --domain devops -- ask -- echo ok`
    Then final_decision should be deny
    And execution should not be attempted