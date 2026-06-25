@pending
Feature: FR-4 Evaluate authorization
  Scenario: Pending -- evaluate returns matched rule reasoning
    Given a policy with a matching authorization rule for a command
    When I run `policyctl evaluate --harness forge --domain devops --action exec --command "git status"`
    Then JSON output should include decision and winning rule metadata
    And reason should reference matched rule