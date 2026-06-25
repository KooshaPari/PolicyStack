@pending
Feature: FR-8 Intercept exit mapping
  Scenario: Pending -- allow/deny/ask mapping
    Given policies producing allow and deny and ask outcomes
    When I run `policyctl intercept` with each outcome scenario
    Then exit_code should map to 0 for allow, 2 for deny, and 3 for ask