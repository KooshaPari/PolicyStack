@pending
Feature: FR-3 Check policy files
  Scenario: Pending -- policy check validates policy files
    Given a valid policy fixture and an invalid policy fixture
    When I run `policyctl check`
    Then I should see successful result for the valid file and an error for invalid inputs