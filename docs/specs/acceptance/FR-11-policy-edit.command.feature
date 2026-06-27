@pending
Feature: FR-11 Policy edit commands
  Scenario: Pending -- add and remove policy rules
    Given a writable policy fixture
    When I run `policyctl add-rule --file policies/test.yaml --id test-allow --effect allow --priority 5 --actions exec`
    Then the rule should be persisted to the file
    When I run `policyctl remove-rule --file policies/test.yaml --id test-allow`
    Then the rule should be removed from the file