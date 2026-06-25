@pending
Feature: FR-12 Policy diff command
  Scenario: Pending -- compare pre/post policy snapshots
    Given two policy files with add/remove/modify/effect changes
    When I run `policyctl diff before.yaml after.yaml`
    Then output should include added_rules, removed_rules, modified_rules, and effect_changes