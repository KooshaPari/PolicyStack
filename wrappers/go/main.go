package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path"
	"strconv"
	"strings"
)

type Rule struct {
	ID                string      `json:"id"`
	Source            string      `json:"source"`
	Action            string      `json:"action"`
	OnMismatch        *string     `json:"on_mismatch"`
	Matcher           string      `json:"matcher"`
	Pattern           string      `json:"pattern"`
	NormalizedPattern string      `json:"normalized_pattern"`
	Conditions        interface{} `json:"conditions"`
	PlatformAction    string      `json:"platform_action"`
	ShellEntry        string      `json:"shell_entry"`
	BashEntry         string      `json:"bash_entry"`
}

type PolicyWrapper struct {
	SchemaVersion      int      `json:"schema_version"`
	RequiredConditions []string `json:"required_conditions"`
	Commands           []Rule   `json:"commands"`
}

type EvalResult struct {
	Command          string   `json:"command"`
	Decision         string   `json:"decision"`
	Matched          bool     `json:"matched"`
	RuleID           string   `json:"rule_id,omitempty"`
	RuleSource       string   `json:"rule_source,omitempty"`
	HasRequired      bool     `json:"has_required"`
	ConditionPassed  bool     `json:"condition_passed"`
	ConditionReasons []string `json:"condition_reasons,omitempty"`
	Error            string   `json:"error,omitempty"`
}

func normalizeCommand(command string) string {
	parts := strings.Fields(command)
	return strings.Join(parts, " ")
}

func runGit(cwd string, args ...string) (string, error) {
	cmd := exec.Command("git", args...)
	if cwd != "" {
		cmd.Dir = cwd
	}
	out, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("%w: %s", err, strings.TrimSpace(string(out)))
	}
	return strings.TrimSpace(string(out)), nil
}

func evalCondition(name string, cwd string) (bool, string, error) {
	switch name {
	case "git_is_worktree":
		output, err := runGit(cwd, "rev-parse", "--is-inside-work-tree")
		if err != nil {
			return false, "git_is_worktree", err
		}
		return output == "true", "git_is_worktree", nil
	case "git_clean_worktree":
		output, err := runGit(cwd, "status", "--porcelain")
		if err != nil {
			return false, "git_clean_worktree", err
		}
		return output == "", "git_clean_worktree", nil
	case "git_synced_to_upstream":
		if _, err := runGit(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"); err != nil {
			return false, "git_synced_to_upstream: no upstream", err
		}
		output, err := runGit(
			cwd,
			"rev-list",
			"--left-right",
			"--count",
			"@{u}...HEAD",
		)
		if err != nil {
			return false, "git_synced_to_upstream: unable to compare upstream", err
		}
		parts := strings.Fields(output)
		if len(parts) != 2 {
			return false, "git_synced_to_upstream: malformed upstream counts", nil
		}
		behind, ahead := parts[0], parts[1]
		if _, err := strconv.Atoi(behind); err != nil {
			return false, "git_synced_to_upstream: malformed behind count", err
		}
		if _, err := strconv.Atoi(ahead); err != nil {
			return false, "git_synced_to_upstream: malformed ahead count", err
		}
		return behind == "0" && ahead == "0", "git_synced_to_upstream", nil
	default:
		return false, "unsupported_condition:" + name, fmt.Errorf("unsupported condition: %s", name)
	}
}

func evalConditionList(
	mode string,
	items []interface{},
	depth int,
	cwd string,
) (bool, []string, bool, error) {
	reasons := make([]string, 0, len(items))
	if len(items) == 0 {
		return true, reasons, false, nil
	}

	hasRequired := false
	passRequired := false
	passOptional := false
	passedAll := true
	var evalErr error

	for _, item := range items {
		itemPassed, itemReasons, itemRequired, itemErr := evalConditionNode(item, depth+1, cwd)
		if !itemRequired {
			if obj, ok := item.(map[string]interface{}); ok {
				if rawAll, ok := obj["all"]; ok {
					if conditions, ok := rawAll.([]interface{}); ok && len(conditions) == 0 {
						itemRequired = true
					}
				}
				if rawAny, ok := obj["any"]; ok {
					if conditions, ok := rawAny.([]interface{}); ok && len(conditions) == 0 {
						itemRequired = true
					}
				}
				if rawMode, ok := obj["mode"]; ok {
					if mode, ok := rawMode.(string); ok && (mode == "all" || mode == "any") {
						if rawConditions, ok := obj["conditions"]; ok {
							if conditions, ok := rawConditions.([]interface{}); ok && len(conditions) == 0 {
								itemRequired = true
							}
						}
					}
				}
			}
		}
		reasons = append(reasons, itemReasons...)
		if itemRequired {
			hasRequired = true
		}
		if itemErr != nil && evalErr == nil {
			evalErr = itemErr
		}

		if mode == "any" {
			if itemPassed {
				if itemRequired {
					passRequired = true
				} else {
					passOptional = true
				}
			}
			continue
		}

		if itemRequired && !itemPassed {
			return false, reasons, true, evalErr
		}
		passedAll = passedAll && itemPassed
	}

	if mode == "any" {
		if passRequired {
			return true, reasons, true, evalErr
		}
		if !hasRequired && passOptional {
			return true, reasons, false, evalErr
		}
		if hasRequired {
			return false, reasons, true, evalErr
		}
		return false, reasons, false, evalErr
	}

	return passedAll, reasons, hasRequired, evalErr
}

func evalConditionNode(value interface{}, depth int, cwd string) (bool, []string, bool, error) {
	if depth > 64 {
		return false, []string{"condition depth limit exceeded"}, false, fmt.Errorf("condition nesting too deep")
	}

	if name, ok := value.(string); ok {
		passed, reason, err := evalCondition(name, cwd)
		if err != nil {
			return false, []string{reason}, true, err
		}
		return passed, []string{reason}, true, nil
	}

	if raw, ok := value.([]interface{}); ok {
		passed, reasons, _, err := evalConditionList("all", raw, depth, cwd)
		return passed, reasons, true, err
	}

	obj, ok := value.(map[string]interface{})
	if !ok {
		return false, []string{"unsupported condition type"}, false, fmt.Errorf("unsupported condition type")
	}

	if rawAll, ok := obj["all"]; ok {
		rawConditions, ok := rawAll.([]interface{})
		if !ok {
			return false, []string{"invalid condition all block"}, false, fmt.Errorf("invalid condition all block")
		}
		return evalConditionList("all", rawConditions, depth, cwd)
	}
	if rawAny, ok := obj["any"]; ok {
		rawConditions, ok := rawAny.([]interface{})
		if !ok {
			return false, []string{"invalid condition any block"}, false, fmt.Errorf("invalid condition any block")
		}
		return evalConditionList("any", rawConditions, depth, cwd)
	}
	if rawMode, ok := obj["mode"]; ok {
		mode, ok := rawMode.(string)
		if !ok || (mode != "all" && mode != "any") {
			return false, []string{"invalid condition mode"}, false, fmt.Errorf("invalid condition mode")
		}
		rawConditions, ok := obj["conditions"]
		if !ok {
			return false, []string{"condition mode requires conditions"}, false, fmt.Errorf("condition mode requires conditions")
		}
		conditions, ok := rawConditions.([]interface{})
		if !ok {
			return false, []string{"invalid condition list"}, false, fmt.Errorf("invalid condition list")
		}
		return evalConditionList(mode, conditions, depth, cwd)
	}

	rawName, ok := obj["name"]
	if !ok {
		return false, []string{"unsupported condition object"}, false, fmt.Errorf("unsupported condition object")
	}
	name, ok := rawName.(string)
	if !ok {
		return false, []string{"invalid condition name"}, false, fmt.Errorf("invalid condition name")
	}

	required := true
	if rawRequired, ok := obj["required"]; ok {
		requiredValue, ok := rawRequired.(bool)
		if !ok {
			return false, []string{"condition.required must be boolean"}, false, fmt.Errorf("condition.required must be boolean")
		}
		required = requiredValue
	}

	passed, reason, err := evalCondition(name, cwd)
	if err != nil {
		return false, []string{reason}, required, err
	}
	return passed, []string{reason}, required, nil
}

func evalConditions(raw interface{}, cwd string) (bool, []string, bool, []string) {
	passed, reasons, hasRequired, evalErr := evalConditionNode(raw, 0, cwd)
	if evalErr != nil {
		return passed, reasons, hasRequired, []string{evalErr.Error()}
	}
	return passed, reasons, hasRequired, nil
}

func matches(rule Rule, command string) bool {
	pattern := normalizeCommand(rule.NormalizedPattern)
	normalized := normalizeCommand(command)
	switch rule.Matcher {
	case "exact":
		return normalized == pattern
	case "prefix":
		return strings.HasPrefix(normalized, pattern)
	case "glob":
		ok, _ := path.Match(pattern, normalized)
		return ok
	default:
		ok, _ := path.Match(pattern, normalized)
		return ok
	}
}

func decisionRank(decision string) int {
	switch decision {
	case "deny":
		return 3
	case "request":
		return 2
	case "allow":
		return 1
	default:
		return 0
	}
}

func evaluate(bundle PolicyWrapper, command string, cwd string) EvalResult {
	normalized := normalizeCommand(command)
	bestDecision := ""
	bestRank := 0
	var bestRule Rule
	var bestReasons []string
	bestError := ""
	bestConditionPassed := true
	bestHasRequired := false
	matched := false

	for _, rule := range bundle.Commands {
		if !matches(rule, normalized) {
			continue
		}
		passed, reasons, hasRequired, evalErrs := evalConditions(rule.Conditions, cwd)
		matched = true

		decision := ""
		conditionPassed := passed
		errText := ""
		switch {
		case evalErrs != nil && len(evalErrs) > 0:
			// Condition evaluation error - default to "request"
			decision = "request"
			conditionPassed = false
		case passed:
			decision = rule.Action
		case rule.OnMismatch != nil && *rule.OnMismatch != "":
			decision = *rule.OnMismatch
		default:
			// Default to "request" when conditions fail and no on_mismatch is set
			decision = "request"
		}

		rank := decisionRank(decision)
		if rank <= bestRank {
			continue
		}

		bestDecision = decision
		bestRank = rank
		bestRule = rule
		bestReasons = reasons
		bestError = errText
		bestConditionPassed = conditionPassed
		bestHasRequired = hasRequired
	}

	if !matched {
		return EvalResult{
			Command:         normalized,
			Matched:         false,
			Decision:        "allow",
			HasRequired:     false,
			ConditionPassed:  true,
			ConditionReasons: nil,
		}
	}

	if bestDecision == "" {
		return EvalResult{
			Command:         normalized,
			Matched:         true,
			Decision:        "allow",
			HasRequired:     false,
			ConditionPassed:  true,
			ConditionReasons: nil,
		}
	}

	return EvalResult{
		Command:          normalized,
		Matched:          true,
		Decision:         bestDecision,
		RuleID:           bestRule.ID,
		RuleSource:       bestRule.Source,
		HasRequired:      bestHasRequired,
		ConditionPassed:   bestConditionPassed,
		ConditionReasons:  bestReasons,
		Error:             bestError,
	}
}

func main() {
	bundlePath := flag.String("bundle", "", "Path to policy-wrapper-rules.json")
	command := flag.String("command", "", "Command to evaluate")
	cwd := flag.String("cwd", "", "Working directory for git checks")
	asJSON := flag.Bool("json", false, "Emit JSON verdict")
	flag.Parse()

	if *bundlePath == "" {
		fmt.Fprintln(os.Stderr, "missing --bundle")
		os.Exit(1)
	}
	if *command == "" {
		fmt.Fprintln(os.Stderr, "missing --command")
		os.Exit(1)
	}

	body, err := os.ReadFile(*bundlePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to read bundle: %v\n", err)
		os.Exit(1)
	}

	var bundle PolicyWrapper
	if err := json.Unmarshal(body, &bundle); err != nil {
		fmt.Fprintf(os.Stderr, "invalid bundle json: %v\n", err)
		os.Exit(1)
	}
	if len(bundle.Commands) == 0 {
		verdict := EvalResult{
			Command:          normalizeCommand(*command),
			Decision:         "allow",
			Matched:          false,
			HasRequired:      false,
			ConditionPassed:  true,
			ConditionReasons: nil,
		}
		if *asJSON {
			out, _ := json.MarshalIndent(verdict, "", "  ")
			fmt.Println(string(out))
		} else {
			fmt.Println(verdict.Decision)
		}
		return
	}

	result := evaluate(bundle, *command, *cwd)
	if *asJSON {
		out, marshalErr := json.MarshalIndent(result, "", "  ")
		if marshalErr != nil {
			fmt.Fprintf(os.Stderr, "failed to marshal result: %v\n", marshalErr)
			os.Exit(1)
		}
		fmt.Println(string(out))
		return
	}
	fmt.Println(result.Decision)
}
