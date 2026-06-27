@pending
Feature: FR-10 Audit filtering and verification
  Scenario: Pending -- audit query and chain check
    Given an audit log with mixed actions and decisions
    When I run `policyctl audit --log-path <fixture> --summary --since 2026-01-01T00:00:00Z --verify-chain`
    Then summary fields total/by_decision/by_action should be present
    And verify-chain result should indicate chain validity