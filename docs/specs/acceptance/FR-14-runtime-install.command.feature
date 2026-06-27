@pending
Feature: FR-14 Runtime integration install/uninstall
  Scenario: Pending -- install and uninstall runtime wrappers
    Given a temporary HOME directory
    When I run `policyctl install-runtime`
    Then install output should report installed wrappers and patched files
    When I run `policyctl uninstall-runtime`
    Then uninstall output should report removed wrappers and launcher restore state