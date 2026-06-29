package main

import (
	"encoding/json"
	"testing"
)

// ---------------------------------------------------------------------------
// normalizeCommand
// ---------------------------------------------------------------------------
func TestNormalizeCommand_Tokens(t *testing.T) {
	if got := normalizeCommand("git push"); got != "git push" {
		t.Errorf("normalizeCommand('git push') = %q, want 'git push'", got)
	}
}

func TestNormalizeCommand_CollapsesSpaces(t *testing.T) {
	if got := normalizeCommand("git   push  -f"); got != "git push -f" {
		t.Errorf("normalizeCommand('git   push  -f') = %q", got)
	}
}

func TestNormalizeCommand_Empty(t *testing.T) {
	if got := normalizeCommand(""); got != "" {
		t.Errorf("normalizeCommand('') = %q, want ''", got)
	}
}

func TestNormalizeCommand_PreservesOrder(t *testing.T) {
	if got := normalizeCommand("a b c"); got != "a b c" {
		t.Errorf("normalizeCommand('a b c') = %q", got)
	}
}

// ---------------------------------------------------------------------------
// decisionRank
// ---------------------------------------------------------------------------
func TestDecisionRank_Deny(t *testing.T) {
	if got := decisionRank("deny"); got != 3 {
		t.Errorf("decisionRank('deny') = %d, want 3", got)
	}
}

func TestDecisionRank_Request(t *testing.T) {
	if got := decisionRank("request"); got != 2 {
		t.Errorf("decisionRank('request') = %d, want 2", got)
	}
}

func TestDecisionRank_Allow(t *testing.T) {
	if got := decisionRank("allow"); got != 1 {
		t.Errorf("decisionRank('allow') = %d, want 1", got)
	}
}

func TestDecisionRank_Unknown(t *testing.T) {
	if got := decisionRank("bogus"); got != 0 {
		t.Errorf("decisionRank('bogus') = %d, want 0", got)
	}
}

// ---------------------------------------------------------------------------
// matchesRule
// ---------------------------------------------------------------------------
func makeRule(id, matcher, pattern string) Rule {
	return Rule{
		ID:                id,
		Source:            "test",
		Action:            "deny",
		Matcher:           matcher,
		Pattern:           pattern,
		NormalizedPattern: pattern,
		Conditions:        []interface{}{},
	}
}

func TestMatchesRule_Exact_Hit(t *testing.T) {
	if !matchesRule(makeRule("r1", "exact", "git push"), "git push") {
		t.Error("exact match should hit")
	}
}

func TestMatchesRule_Exact_Miss(t *testing.T) {
	if matchesRule(makeRule("r1", "exact", "git push"), "git pull") {
		t.Error("exact match should miss")
	}
}

func TestMatchesRule_Exact_NormalizesInput(t *testing.T) {
	if !matchesRule(makeRule("r1", "exact", "git push"), "  git   push  ") {
		t.Error("exact match should normalize input")
	}
}

func TestMatchesRule_Prefix_Hit(t *testing.T) {
	if !matchesRule(makeRule("r1", "prefix", "git"), "git push -f") {
		t.Error("prefix match should hit")
	}
}

func TestMatchesRule_Prefix_Miss(t *testing.T) {
	if matchesRule(makeRule("r1", "prefix", "git"), "got push") {
		t.Error("prefix match should miss")
	}
}

func TestMatchesRule_Glob_Wildcard(t *testing.T) {
	if !matchesRule(makeRule("r1", "glob", "git *"), "git push") {
		t.Error("glob match should hit")
	}
}

func TestMatchesRule_Glob_Miss(t *testing.T) {
	if matchesRule(makeRule("r1", "glob", "git *"), "hg push") {
		t.Error("glob match should miss")
	}
}

// ---------------------------------------------------------------------------
// evalConditionNode — depth guard
// ---------------------------------------------------------------------------
func TestEvalConditionNode_DepthLimit(t *testing.T) {
	passed, reasons, hasRequired, err := evalConditionNode("anything", 999, "")
	if passed {
		t.Error("expected not passed at depth limit")
	}
	if err == nil || err.Error() != "nesting-too-deep" {
		t.Errorf("expected nesting-too-deep error, got %v", err)
	}
	if hasRequired {
		t.Error("expected hasRequired=false at depth limit")
	}
	if len(reasons) == 0 {
		t.Error("expected reasons")
	}
}

// ---------------------------------------------------------------------------
// evalConditionNode — string (leaf)
// ---------------------------------------------------------------------------
func TestEvalConditionNode_String_Unknown(t *testing.T) {
	passed, reasons, hasRequired, err := evalConditionNode("nonexistent", 0, "")
	if passed {
		t.Error("expected not passed for unknown condition")
	}
	if !hasRequired {
		t.Error("expected hasRequired=true for string condition")
	}
	if err == nil {
		t.Error("expected error for unknown condition")
	}
	if len(reasons) == 0 {
		t.Error("expected reasons")
	}
}

// ---------------------------------------------------------------------------
// evalConditionNode — array (treated as mode "all")
// ---------------------------------------------------------------------------
func TestEvalConditionNode_Array_Empty(t *testing.T) {
	passed, reasons, hasRequired, err := evalConditionNode([]interface{}{}, 0, "")
	if !passed {
		t.Error("expected passed for empty array")
	}
	if !hasRequired {
		t.Error("expected hasRequired=true for implicit-all array")
	}
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
	if len(reasons) != 0 {
		t.Errorf("expected empty reasons, got %v", reasons)
	}
}

func TestEvalConditionNode_Array_NonEmpty(t *testing.T) {
	passed, _, _, _ := evalConditionNode(
		[]interface{}{"nonexistent_cond"},
		0, "",
	)
	if passed {
		t.Error("expected not passed for unknown condition in array")
	}
}

// ---------------------------------------------------------------------------
// evalConditionNode — object { "all": … }
// ---------------------------------------------------------------------------
func TestEvalConditionNode_All_Empty(t *testing.T) {
	passed, _, _, _ := evalConditionNode(
		map[string]interface{}{"all": []interface{}{}},
		0, "",
	)
	if !passed {
		t.Error("expected passed for empty all block")
	}
}

func TestEvalConditionNode_All_InvalidType(t *testing.T) {
	_, _, _, err := evalConditionNode(
		map[string]interface{}{"all": 42},
		0, "",
	)
	if err == nil || err.Error() != "invalid-all-list" {
		t.Errorf("expected invalid-all-list error, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// evalConditionNode — object { "any": … }
// ---------------------------------------------------------------------------
func TestEvalConditionNode_Any_Empty(t *testing.T) {
	passed, _, _, _ := evalConditionNode(
		map[string]interface{}{"any": []interface{}{}},
		0, "",
	)
	if !passed {
		t.Error("expected passed for empty any block")
	}
}

func TestEvalConditionNode_Any_InvalidType(t *testing.T) {
	_, _, _, err := evalConditionNode(
		map[string]interface{}{"any": 42},
		0, "",
	)
	if err == nil || err.Error() != "invalid-any-list" {
		t.Errorf("expected invalid-any-list error, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// evalConditionNode — object { "mode": …, "conditions": … }
// ---------------------------------------------------------------------------
func TestEvalConditionNode_ModeAll_Empty(t *testing.T) {
	passed, _, _, _ := evalConditionNode(
		map[string]interface{}{
			"mode":       "all",
			"conditions": []interface{}{},
		},
		0, "",
	)
	if !passed {
		t.Error("expected passed for mode=all with empty conditions")
	}
}

func TestEvalConditionNode_ModeAny_Empty(t *testing.T) {
	passed, _, _, _ := evalConditionNode(
		map[string]interface{}{
			"mode":       "any",
			"conditions": []interface{}{},
		},
		0, "",
	)
	if !passed {
		t.Error("expected passed for mode=any with empty conditions")
	}
}

func TestEvalConditionNode_Mode_NotAString(t *testing.T) {
	_, _, _, err := evalConditionNode(
		map[string]interface{}{
			"mode":       42,
			"conditions": []interface{}{},
		},
		0, "",
	)
	if err == nil || err.Error() != "invalid-mode-type" {
		t.Errorf("expected invalid-mode-type error, got %v", err)
	}
}

func TestEvalConditionNode_Mode_Unsupported(t *testing.T) {
	_, _, _, err := evalConditionNode(
		map[string]interface{}{
			"mode":       "maybe",
			"conditions": []interface{}{},
		},
		0, "",
	)
	if err == nil {
		t.Error("expected error for unsupported mode")
	}
}

func TestEvalConditionNode_Mode_MissingConditions(t *testing.T) {
	_, _, _, err := evalConditionNode(
		map[string]interface{}{"mode": "all"},
		0, "",
	)
	if err == nil || err.Error() != "missing-conditions" {
		t.Errorf("expected missing-conditions error, got %v", err)
	}
}

func TestEvalConditionNode_Mode_ConditionsNotList(t *testing.T) {
	_, _, _, err := evalConditionNode(
		map[string]interface{}{
			"mode":       "all",
			"conditions": 99,
		},
		0, "",
	)
	if err == nil || err.Error() != "conditions-not-list" {
		t.Errorf("expected conditions-not-list error, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// evalConditionNode — object { "name": …, "required": … }
// ---------------------------------------------------------------------------
func TestEvalConditionNode_MissingName(t *testing.T) {
	_, _, _, err := evalConditionNode(
		map[string]interface{}{"foo": "bar"},
		0, "",
	)
	if err == nil || err.Error() != "unsupported-object" {
		t.Errorf("expected unsupported-object error, got %v", err)
	}
}

func TestEvalConditionNode_NameNotString(t *testing.T) {
	_, _, _, err := evalConditionNode(
		map[string]interface{}{"name": 42},
		0, "",
	)
	if err == nil || err.Error() != "invalid-name-type" {
		t.Errorf("expected invalid-name-type error, got %v", err)
	}
}

func TestEvalConditionNode_RequiredNotBool(t *testing.T) {
	_, _, _, err := evalConditionNode(
		map[string]interface{}{"name": "x", "required": 99},
		0, "",
	)
	if err == nil || err.Error() != "required-not-bool" {
		t.Errorf("expected required-not-bool error, got %v", err)
	}
}

func TestEvalConditionNode_OptionalCond_Unknown(t *testing.T) {
	passed, reasons, hasRequired, _ := evalConditionNode(
		map[string]interface{}{"name": "unknown_cond", "required": false},
		0, "",
	)
	if passed {
		t.Error("expected not passed for unknown optional condition")
	}
	if hasRequired {
		t.Error("expected hasRequired=false for optional condition")
	}
	if len(reasons) == 0 {
		t.Error("expected reasons")
	}
}

// ---------------------------------------------------------------------------
// evalConditions (top-level wrapper)
// ---------------------------------------------------------------------------
func TestEvalConditions_EmptyArray(t *testing.T) {
	passed, reasons, hasRequired, errs := evalConditions([]interface{}{}, "")
	if !passed {
		t.Error("expected passed for empty array conditions")
	}
	if !hasRequired {
		t.Error("expected hasRequired=true for empty array (implicit required)")
	}
	if len(errs) > 0 {
		t.Errorf("expected no errors, got %v", errs)
	}
	if len(reasons) > 0 {
		t.Errorf("expected no reasons for empty, got %v", reasons)
	}
}

// ---------------------------------------------------------------------------
// evaluate — no rules
// ---------------------------------------------------------------------------
func TestEvaluate_NoRules(t *testing.T) {
	b := PolicyWrapper{Commands: []Rule{}}
	r := evaluate(b, "git push", "")
	if r.Decision != "allow" {
		t.Errorf("expected decision=allow, got %s", r.Decision)
	}
	if r.Matched {
		t.Error("expected matched=false for no rules")
	}
}

// ---------------------------------------------------------------------------
// evaluate — exact allow
// ---------------------------------------------------------------------------
func TestEvaluate_ExactAllow(t *testing.T) {
	b := PolicyWrapper{
		Commands: []Rule{
			{
				ID:                "r1",
				Source:            "test",
				Action:            "allow",
				Matcher:           "exact",
				NormalizedPattern: "git push",
				Conditions:        []interface{}{},
			},
		},
	}
	r := evaluate(b, "git push", "")
	if r.Decision != "allow" {
		t.Errorf("expected decision=allow, got %s", r.Decision)
	}
	if !r.Matched {
		t.Error("expected matched=true")
	}
	if r.RuleID != "r1" {
		t.Errorf("expected ruleID=r1, got %s", r.RuleID)
	}
}

// ---------------------------------------------------------------------------
// evaluate — deny overrides allow (highest rank wins)
// ---------------------------------------------------------------------------
func TestEvaluate_DenyOverridesAllow(t *testing.T) {
	b := PolicyWrapper{
		Commands: []Rule{
			{
				ID:                "allow_all",
				Source:            "test",
				Action:            "allow",
				Matcher:           "prefix",
				NormalizedPattern: "git",
				Conditions:        []interface{}{},
			},
			{
				ID:                "deny_force",
				Source:            "test",
				Action:            "deny",
				Matcher:           "exact",
				NormalizedPattern: "git push -f",
				Conditions:        []interface{}{},
			},
		},
	}
	r := evaluate(b, "git push -f", "")
	if r.Decision != "deny" {
		t.Errorf("expected decision=deny, got %s", r.Decision)
	}
	if r.RuleID != "deny_force" {
		t.Errorf("expected ruleID=deny_force, got %s", r.RuleID)
	}
}

// ---------------------------------------------------------------------------
// evaluate — condition error produces "request"
// ---------------------------------------------------------------------------
func TestEvaluate_ConditionError_Requests(t *testing.T) {
	b := PolicyWrapper{
		Commands: []Rule{
			{
				ID:                "r1",
				Source:            "test",
				Action:            "allow",
				OnMismatch:        strPtr("deny"),
				Matcher:           "exact",
				NormalizedPattern: "risky",
				Conditions:        "unknown_condition_xyz",
			},
		},
	}
	r := evaluate(b, "risky", "")
	if r.Decision != "request" {
		t.Errorf("expected decision=request (error path), got %s", r.Decision)
	}
	if !r.Matched {
		t.Error("expected matched=true")
	}
}

// ---------------------------------------------------------------------------
// evaluate — no matching rule defaults to allow
// ---------------------------------------------------------------------------
func TestEvaluate_NoMatchingRule(t *testing.T) {
	b := PolicyWrapper{
		Commands: []Rule{
			{
				ID:                "r1",
				Source:            "test",
				Action:            "deny",
				Matcher:           "exact",
				NormalizedPattern: "git push",
				Conditions:        []interface{}{},
			},
		},
	}
	r := evaluate(b, "hg pull", "")
	if r.Decision != "allow" {
		t.Errorf("expected decision=allow for unmatched command, got %s", r.Decision)
	}
	if r.Matched {
		t.Error("expected matched=false for unmatched command")
	}
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
func strPtr(s string) *string { return &s }

// ---------------------------------------------------------------------------
// JSON round-trip for EvalResult
// ---------------------------------------------------------------------------
func TestEvalResult_JSONSerialization(t *testing.T) {
	r := EvalResult{
		Command:          "test cmd",
		Decision:         "deny",
		Matched:          true,
		RuleID:           "r1",
		RuleSource:       "test",
		HasRequired:      true,
		ConditionPassed:  false,
		ConditionReasons: []string{"reason1"},
		Error:            "some error",
	}
	data, err := json.Marshal(r)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}
	var r2 EvalResult
	if err := json.Unmarshal(data, &r2); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if r2.Command != r.Command {
		t.Errorf("Command: got %q, want %q", r2.Command, r.Command)
	}
	if r2.Decision != r.Decision {
		t.Errorf("Decision: got %q, want %q", r2.Decision, r.Decision)
	}
	if r2.Matched != r.Matched {
		t.Errorf("Matched: got %v, want %v", r2.Matched, r.Matched)
	}
}

// ---------------------------------------------------------------------------
// PolicyWrapper JSON unmarshal
// ---------------------------------------------------------------------------
func TestPolicyWrapper_JSONRoundTrip(t *testing.T) {
	input := `{
		"schema_version": 1,
		"required_conditions": ["git_clean_worktree"],
		"commands": [
			{
				"id": "r1",
				"source": "test",
				"action": "deny",
				"matcher": "exact",
				"pattern": "git push",
				"normalized_pattern": "git push",
				"conditions": [],
				"platform_action": "",
				"shell_entry": "",
				"bash_entry": ""
			}
		]
	}`
	var b PolicyWrapper
	if err := json.Unmarshal([]byte(input), &b); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if b.SchemaVersion != 1 {
		t.Errorf("SchemaVersion: got %d, want 1", b.SchemaVersion)
	}
	if len(b.Commands) != 1 {
		t.Errorf("expected 1 command, got %d", len(b.Commands))
	}
}

// ---------------------------------------------------------------------------
// evalCondition — unknown condition produces error
// ---------------------------------------------------------------------------
func TestEvalCondition_Unknown(t *testing.T) {
	_, reason, err := evalCondition("foobar", "")
	if err == nil {
		t.Error("expected error for unknown condition")
	}
	if reason != "unsupported-condition:foobar" {
		t.Errorf("expected reason unsupported-condition:foobar, got %s", reason)
	}
}

// ---------------------------------------------------------------------------
// Rule on_mismatch fallback
// ---------------------------------------------------------------------------
func TestEvaluate_OnMismatchFallback(t *testing.T) {
	// A condition that fails without error and has on_mismatch set.
	// Since unknown conditions produce errors (→ "request"), this tests
	// that the error path takes priority.
	b := PolicyWrapper{
		Commands: []Rule{
			{
				ID:                "r1",
				Source:            "test",
				Action:            "allow",
				OnMismatch:        strPtr("deny"),
				Matcher:           "exact",
				NormalizedPattern: "cmd",
				Conditions:        "unknown_condition_xyz",
			},
		},
	}
	r := evaluate(b, "cmd", "")
	if r.Decision != "request" {
		t.Errorf("expected decision=request for errored condition, got %s", r.Decision)
	}
}
