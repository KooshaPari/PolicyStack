@pending
Feature: FR-2 Manifest layer discovery
  Scenario: Pending -- manifest command lists layers
    Given a repository fixture with harness/domain policy layers
    When I run `policyctl manifest --harness forge --domain devops`
    Then the output should include ordered layer scope names and source file paths