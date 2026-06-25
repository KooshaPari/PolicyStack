@pending
Feature: FR-1 Resolve policy contract
  Scenario: Pending -- resolve command payload
    Given a repository fixture with layered policy files
    When I run `policyctl resolve --harness forge --domain devops`
    Then I should receive JSON with keys policy_hash, scope_chain, policy, source_files, resolved_at
    And final decision should be emitted via JSON mode
