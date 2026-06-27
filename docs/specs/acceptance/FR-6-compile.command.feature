@pending
Feature: FR-6 Compile policy to target
  Scenario: Pending -- compile creates native config and shim rules
    Given a policy with conditional and runtime-only rules
    When I run `policyctl compile --target claude-code --harness forge --domain devops`
    Then output should include target, defaults, native_config, and shim_rules fields
    And shim_rules should include non-native-rule entries