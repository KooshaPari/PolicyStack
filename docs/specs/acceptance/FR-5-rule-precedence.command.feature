@pending
Feature: FR-5 Rule precedence
  Scenario: Pending -- deny precedence over lower effect
    Given two authorization rules with the same priority but different effects
    When I run `policyctl evaluate --harness forge --domain devops --action exec --command "rm -rf /tmp/test"`
    Then deny should win when a tie for priority exists
    And output should include ordered matching rules