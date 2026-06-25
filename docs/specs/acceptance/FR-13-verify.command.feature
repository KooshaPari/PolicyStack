@pending
Feature: FR-13 Verify baseline hash
  Scenario: Pending -- baseline tamper detection
    Given a policies directory with existing policy files
    When I run `policyctl verify`
    Then status should become baseline-recorded
    And a second run without changes should return ok
    And after touching a file should return tampered and non-zero