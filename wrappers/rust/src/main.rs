// SPDX-License-Identifier: MIT OR Apache-2.0
// Copyright (c) 2026 Koosha Pari

use clap::Parser;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::process::{Command, Stdio};
use std::{fs, path::PathBuf, process};

#[derive(Debug, Serialize, Deserialize, Clone)]
struct Rule {
    id: String,
    source: String,
    action: String,
    on_mismatch: Option<String>,
    matcher: String,
    pattern: String,
    normalized_pattern: String,
    conditions: Value,
    platform_action: String,
    shell_entry: String,
    bash_entry: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct PolicyWrapper {
    schema_version: i32,
    #[serde(default)]
    required_conditions: Vec<String>,
    commands: Vec<Rule>,
}

#[derive(Serialize)]
struct EvalResult {
    command: String,
    decision: String,
    matched: bool,
    #[serde(skip_serializing_if = "String::is_empty")]
    rule_id: String,
    #[serde(skip_serializing_if = "String::is_empty")]
    rule_source: String,
    has_required: bool,
    condition_passed: bool,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    condition_reasons: Vec<String>,
    #[serde(skip_serializing_if = "String::is_empty")]
    error: String,
}

#[derive(Debug)]
struct ConditionEval {
    passed: bool,
    reasons: Vec<String>,
    has_required: bool,
    error: Option<String>,
}

const MAX_CONDITION_DEPTH: usize = 64;

#[derive(Parser)]
#[command(version, about)]
struct Args {
    /// Path to generated policy-wrapper-rules.json
    #[arg(long)]
    bundle: PathBuf,

    /// Command to evaluate
    #[arg(long, allow_hyphen_values = true)]
    command: String,

    /// Working directory for git evaluations
    #[arg(long)]
    cwd: Option<PathBuf>,

    /// Output JSON verdict
    #[arg(long, default_value_t = false)]
    json: bool,
}

fn normalize_command(command: &str) -> String {
    command.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn run_git(cwd: Option<&PathBuf>, args: &[&str]) -> Result<String, String> {
    let mut cmd = Command::new("git");
    cmd.args(args);
    if let Some(dir) = cwd {
        cmd.current_dir(dir);
    }
    let output = cmd
        .stderr(Stdio::piped())
        .output()
        .map_err(|e| format!("failed to execute git: {e}"))?;
    if !output.status.success() {
        let err = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(err);
    }
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn eval_condition(name: &str, cwd: Option<&PathBuf>) -> Result<bool, String> {
    match name {
        "git_is_worktree" => Ok(run_git(cwd, &["rev-parse", "--is-inside-work-tree"])?.eq("true")),
        "git_clean_worktree" => Ok(run_git(cwd, &["status", "--porcelain"])?.is_empty()),
        "git_synced_to_upstream" => {
            run_git(
                cwd,
                &["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            )
            .map_err(|_| "git-no-upstream".to_string())?;
            let counts = run_git(cwd, &["rev-list", "--left-right", "--count", "@{u}...HEAD"])
                .map_err(|_| "git-upstream-compare-failed".to_string())?;
            let mut it = counts.split_whitespace();
            let behind = it
                .next()
                .ok_or_else(|| "git-behind-not-found".to_string())?;
            let ahead = it.next().ok_or_else(|| "git-ahead-not-found".to_string())?;
            if it.next().is_some() {
                return Ok(false);
            }
            behind
                .parse::<i64>()
                .map_err(|_| "git-behind-parse-error".to_string())?;
            ahead
                .parse::<i64>()
                .map_err(|_| "git-ahead-parse-error".to_string())?;
            if behind != "0" || ahead != "0" {
                return Ok(false);
            }
            Ok(true)
        }
        _ => Err(format!("unsupported-condition:{}", name.replace('_', "-"))),
    }
}

fn is_empty_condition_group(value: &Value) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };

    if let Some(all) = object.get("all") {
        return all.as_array().is_some_and(std::vec::Vec::is_empty);
    }
    if let Some(any) = object.get("any") {
        return any.as_array().is_some_and(std::vec::Vec::is_empty);
    }
    if let Some(mode) = object.get("mode") {
        let Some(raw_mode) = mode.as_str() else {
            return false;
        };
        if !matches!(raw_mode, "all" | "any") {
            return false;
        }
        return object
            .get("conditions")
            .and_then(Value::as_array)
            .is_some_and(std::vec::Vec::is_empty);
    }
    false
}

fn eval_condition_list(
    mode: &str,
    conditions: &[Value],
    cwd: Option<&PathBuf>,
    depth: usize,
) -> ConditionEval {
    let mut reasons = Vec::new();
    if conditions.is_empty() {
        return ConditionEval {
            passed: true,
            reasons,
            has_required: false,
            error: None,
        };
    }

    let mut pass_required = false;
    let mut pass_optional = false;
    let mut has_required = false;
    let mut first_error = None;

    for condition in conditions {
        let child = eval_condition_node(condition, cwd, depth + 1);
        let mut child_required = child.has_required;
        if !child_required && is_empty_condition_group(condition) {
            child_required = true;
        }
        reasons.extend(child.reasons);

        if child.error.is_some() && first_error.is_none() {
            first_error = child.error;
        }

        if child_required {
            has_required = true;
            if !child.passed && mode == "all" {
                return ConditionEval {
                    passed: false,
                    reasons,
                    has_required,
                    error: first_error,
                };
            }
        }

        if child.passed {
            if child_required {
                pass_required = true;
            } else {
                pass_optional = true;
            }
        }
    }

    if mode == "any" {
        let passed = pass_required || (!has_required && pass_optional);
        return ConditionEval {
            passed,
            reasons,
            has_required,
            error: first_error,
        };
    }

    ConditionEval {
        passed: true,
        reasons,
        has_required,
        error: first_error,
    }
}

fn eval_condition_node(value: &Value, cwd: Option<&PathBuf>, depth: usize) -> ConditionEval {
    if depth > MAX_CONDITION_DEPTH {
        return ConditionEval {
            passed: false,
            reasons: vec!["condition depth limit exceeded".to_string()],
            has_required: false,
            error: Some("nesting-too-deep".to_string()),
        };
    }

    if let Some(name) = value.as_str() {
        let mut result = ConditionEval {
            passed: false,
            reasons: vec![name.to_string()],
            has_required: true,
            error: None,
        };
        match eval_condition(name, cwd) {
            Ok(ok) => result.passed = ok,
            Err(err) => {
                if let Some(reason) = result.reasons.first() {
                    result.reasons[0] = format!("{}: {}", reason, err);
                }
                result.error = Some(err);
            }
        }
        return result;
    }

    if let Some(items) = value.as_array() {
        let mut result = eval_condition_list("all", items, cwd, depth);
        result.has_required = true;
        return result;
    }

    if let Some(object) = value.as_object() {
        if let Some(raw_all) = object.get("all") {
            if let Some(items) = raw_all.as_array() {
                let result = eval_condition_list("all", items, cwd, depth);
                return result;
            }
            return ConditionEval {
                passed: false,
                reasons: vec!["invalid condition list for all".to_string()],
                has_required: false,
                error: Some("invalid-all-list".to_string()),
            };
        }

        if let Some(raw_any) = object.get("any") {
            if let Some(items) = raw_any.as_array() {
                let result = eval_condition_list("any", items, cwd, depth);
                return result;
            }
            return ConditionEval {
                passed: false,
                reasons: vec!["invalid condition list for any".to_string()],
                has_required: false,
                error: Some("invalid-any-list".to_string()),
            };
        }

        if object.contains_key("mode") {
            let Some(mode) = object.get("mode").and_then(Value::as_str) else {
                return ConditionEval {
                    passed: false,
                    reasons: vec!["invalid condition mode".to_string()],
                    has_required: false,
                    error: Some("invalid-mode-type".to_string()),
                };
            };
            if mode != "all" && mode != "any" {
                return ConditionEval {
                    passed: false,
                    reasons: vec![format!("unsupported condition mode: {}", mode)],
                    has_required: false,
                    error: Some(format!("unsupported-mode:{}", mode)),
                };
            }

            let Some(raw_conditions) = object.get("conditions") else {
                return ConditionEval {
                    passed: false,
                    reasons: vec!["condition mode missing conditions".to_string()],
                    has_required: false,
                    error: Some("missing-conditions".to_string()),
                };
            };
            let Some(items) = raw_conditions.as_array() else {
                return ConditionEval {
                    passed: false,
                    reasons: vec!["condition mode conditions must be list".to_string()],
                    has_required: false,
                    error: Some("conditions-not-list".to_string()),
                };
            };
            let result = eval_condition_list(mode, items, cwd, depth);
            return result;
        }

        let Some(name) = object.get("name").and_then(Value::as_str) else {
            return ConditionEval {
                passed: false,
                reasons: vec!["unsupported condition object".to_string()],
                has_required: false,
                error: Some("unsupported-object".to_string()),
            };
        };
        let required = if let Some(raw_required) = object.get("required") {
            let Some(value) = raw_required.as_bool() else {
                return ConditionEval {
                    passed: false,
                    reasons: vec!["condition.required must be boolean".to_string()],
                    has_required: false,
                    error: Some("required-not-bool".to_string()),
                };
            };
            value
        } else {
            true
        };

        let mut result = ConditionEval {
            passed: false,
            reasons: vec![name.to_string()],
            has_required: required,
            error: None,
        };
        match eval_condition(name, cwd) {
            Ok(ok) => result.passed = ok,
            Err(err) => {
                result.reasons[0] = format!("{}: {}", name, err);
                result.error = Some(err);
            }
        }
        return result;
    }

    ConditionEval {
        passed: false,
        reasons: vec!["unsupported condition type".to_string()],
        has_required: false,
        error: Some("unsupported-type".to_string()),
    }
}

fn matches_rule(rule: &Rule, command: &str) -> bool {
    let normalized = normalize_command(command);
    let pattern = normalize_command(&rule.normalized_pattern);

    match rule.matcher.as_str() {
        "exact" => normalized == pattern,
        "prefix" => normalized.starts_with(&pattern),
        "glob" => fnmatch::fnmatch(&normalized, &pattern).unwrap_or(false),
        _ => normalized == pattern,
    }
}

fn decision_rank(decision: &str) -> u8 {
    match decision {
        "deny" => 3,
        "request" => 2,
        "allow" => 1,
        _ => 0,
    }
}

fn evaluate(bundle: &PolicyWrapper, command: &str, cwd: Option<&PathBuf>) -> EvalResult {
    let normalized = normalize_command(command);
    let mut best_rank = 0u8;
    let mut best_decision = String::new();
    let mut best_rule = None;
    let mut best_condition_passed = true;
    let mut best_has_required = false;
    let mut best_reasons: Vec<String> = Vec::new();
    let mut best_error = String::new();
    let mut matched = false;

    for rule in &bundle.commands {
        if !matches_rule(rule, &normalized) {
            continue;
        }
        matched = true;

        let evaluated = eval_condition_node(&rule.conditions, cwd, 0);
        let cond_ok = evaluated.passed;
        let reasons = evaluated.reasons;
        let cond_error = evaluated.error;
        let mut decision = String::new();
        let mut condition_passed = cond_ok;
        let mut error = String::new();

        if let Some(err) = cond_error {
            condition_passed = false;
            error = err;
            decision = "request".to_string();
        } else if cond_ok {
            decision = rule.action.clone();
        } else if let Some(fallback) = rule.on_mismatch.as_deref() {
            if !fallback.is_empty() {
                decision = fallback.to_string();
            }
        }
        if decision.is_empty() {
            continue;
        }

        let rank = decision_rank(&decision);
        if rank > best_rank {
            best_rank = rank;
            best_decision = decision;
            best_rule = Some(rule);
            best_condition_passed = condition_passed;
            best_has_required = evaluated.has_required;
            best_reasons = reasons;
            best_error = error;
        }
    }

    if !matched {
        return EvalResult {
            command: normalized,
            decision: "allow".to_string(),
            matched: false,
            rule_id: String::new(),
            rule_source: String::new(),
            has_required: false,
            condition_passed: true,
            condition_reasons: Vec::new(),
            error: String::new(),
        };
    }

    if best_decision.is_empty() {
        return EvalResult {
            command: normalized,
            decision: "allow".to_string(),
            matched: true,
            rule_id: String::new(),
            rule_source: String::new(),
            has_required: false,
            condition_passed: true,
            condition_reasons: Vec::new(),
            error: String::new(),
        };
    }

    EvalResult {
        command: normalized,
        decision: best_decision,
        matched: true,
        rule_id: best_rule.map_or_else(String::new, |rule| rule.id.clone()),
        rule_source: best_rule.map_or_else(String::new, |rule| rule.source.clone()),
        has_required: best_has_required,
        condition_passed: best_condition_passed,
        condition_reasons: best_reasons,
        error: best_error,
    }
}

fn main() {
    let args = Args::parse();
    if args.command.trim().is_empty() {
        eprintln!("--command is required");
        process::exit(1);
    }

    let raw = match fs::read_to_string(&args.bundle) {
        Ok(value) => value,
        Err(err) => {
            eprintln!("failed to read bundle: {}", err);
            process::exit(1);
        }
    };

    let bundle: PolicyWrapper = match serde_json::from_str(&raw) {
        Ok(value) => value,
        Err(err) => {
            eprintln!("invalid bundle JSON: {}", err);
            process::exit(1);
        }
    };

    let result = evaluate(&bundle, &args.command, args.cwd.as_ref());

    if args.json {
        match serde_json::to_string_pretty(&result) {
            Ok(json) => println!("{}", json),
            Err(err) => {
                eprintln!("failed to encode output: {}", err);
                process::exit(1);
            }
        }
    } else {
        println!("{}", result.decision);
    }
}

mod fnmatch {
    pub fn fnmatch(text: &str, pattern: &str) -> Result<bool, ()> {
        fn match_class(text: u8, class: &[u8]) -> bool {
            if class.is_empty() {
                return false;
            }

            let mut idx = 0;
            let mut matched = false;
            while idx < class.len() {
                if class[idx] == b'\\' {
                    if idx + 1 >= class.len() {
                        return false;
                    }
                    if text == class[idx + 1] {
                        matched = true;
                    }
                    idx += 2;
                    continue;
                }

                if idx + 2 < class.len() && class[idx + 1] == b'-' {
                    let start = class[idx];
                    let end = class[idx + 2];
                    if text >= start && text <= end {
                        matched = true;
                    }
                    idx += 3;
                    continue;
                }

                if text == class[idx] {
                    matched = true;
                }
                idx += 1;
            }
            matched
        }

        fn rec(text: &[u8], pat: &[u8], ti: usize, pi: usize) -> bool {
            if pi == pat.len() {
                return ti == text.len();
            }
            match pat[pi] as char {
                '*' => {
                    let mut idx = ti;
                    while idx <= text.len() {
                        if rec(text, pat, idx, pi + 1) {
                            return true;
                        }
                        idx += 1;
                    }
                    false
                }
                '?' => {
                    if ti >= text.len() {
                        return false;
                    }
                    rec(text, pat, ti + 1, pi + 1)
                }
                '\\' => {
                    if pi + 1 >= pat.len() || ti >= text.len() {
                        return false;
                    }
                    if pat[pi + 1] == text[ti] {
                        rec(text, pat, ti + 1, pi + 2)
                    } else {
                        false
                    }
                }
                '[' => {
                    let mut closing = pi + 1;
                    while closing < pat.len() && pat[closing] != b']' {
                        closing += 1;
                    }
                    if closing >= pat.len() {
                        return false;
                    }
                    if ti >= text.len() {
                        return false;
                    }
                    let class = &pat[pi + 1..closing];
                    let ok = match_class(text[ti], class);
                    if ok {
                        rec(text, pat, ti + 1, closing + 1)
                    } else {
                        false
                    }
                }
                c => {
                    if ti >= text.len() || c as u8 != text[ti] {
                        false
                    } else {
                        rec(text, pat, ti + 1, pi + 1)
                    }
                }
            }
        }
        Ok(rec(text.as_bytes(), pattern.as_bytes(), 0, 0))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    // -----------------------------------------------------------------------
    // normalize_command
    // -----------------------------------------------------------------------
    #[test]
    fn test_normalize_command_trims_whitespace() {
        assert_eq!(normalize_command("git push"), "git push");
    }

    #[test]
    fn test_normalize_command_collapses_multiple_spaces() {
        assert_eq!(normalize_command("git   push  -f"), "git push -f");
    }

    #[test]
    fn test_normalize_command_handles_empty() {
        assert_eq!(normalize_command(""), "");
    }

    #[test]
    fn test_normalize_command_preserves_order() {
        assert_eq!(normalize_command("a b c"), "a b c");
    }

    // -----------------------------------------------------------------------
    // decision_rank
    // -----------------------------------------------------------------------
    #[test]
    fn test_decision_rank_deny_highest() {
        assert_eq!(decision_rank("deny"), 3);
    }

    #[test]
    fn test_decision_rank_request_second() {
        assert_eq!(decision_rank("request"), 2);
    }

    #[test]
    fn test_decision_rank_allow_third() {
        assert_eq!(decision_rank("allow"), 1);
    }

    #[test]
    fn test_decision_rank_unknown_is_zero() {
        assert_eq!(decision_rank("bogus"), 0);
    }

    #[test]
    fn test_decision_rank_empty_is_zero() {
        assert_eq!(decision_rank(""), 0);
    }

    // -----------------------------------------------------------------------
    // matches_rule
    // -----------------------------------------------------------------------
    fn make_rule(id: &str, matcher: &str, pattern: &str) -> Rule {
        Rule {
            id: id.into(),
            source: "test".into(),
            action: "deny".into(),
            on_mismatch: None,
            matcher: matcher.into(),
            pattern: pattern.into(),
            normalized_pattern: pattern.into(),
            conditions: json!([]),
            platform_action: String::new(),
            shell_entry: String::new(),
            bash_entry: String::new(),
        }
    }

    #[test]
    fn test_matches_rule_exact_hit() {
        assert!(matches_rule(
            &make_rule("r1", "exact", "git push"),
            "git push"
        ));
    }

    #[test]
    fn test_matches_rule_exact_miss() {
        assert!(!matches_rule(
            &make_rule("r1", "exact", "git push"),
            "git pull"
        ));
    }

    #[test]
    fn test_matches_rule_exact_normalizes_input() {
        assert!(matches_rule(
            &make_rule("r1", "exact", "git push"),
            "  git   push  "
        ));
    }

    #[test]
    fn test_matches_rule_prefix_hit() {
        assert!(matches_rule(
            &make_rule("r1", "prefix", "git"),
            "git push -f"
        ));
    }

    #[test]
    fn test_matches_rule_prefix_miss() {
        assert!(!matches_rule(&make_rule("r1", "prefix", "git"), "got push"));
    }

    #[test]
    fn test_matches_rule_prefix_empty_input() {
        assert!(!matches_rule(&make_rule("r1", "prefix", "git"), ""));
    }

    #[test]
    fn test_matches_rule_glob_wildcard() {
        assert!(matches_rule(&make_rule("r1", "glob", "git *"), "git push"));
    }

    #[test]
    fn test_matches_rule_glob_miss() {
        assert!(!matches_rule(&make_rule("r1", "glob", "git *"), "hg push"));
    }

    #[test]
    fn test_matches_rule_unknown_matcher_defaults_exact() {
        let rule = make_rule("r1", "regex", "git push");
        assert!(matches_rule(&rule, "git push"));
    }

    // -----------------------------------------------------------------------
    // is_empty_condition_group
    // -----------------------------------------------------------------------
    #[test]
    fn test_empty_group_value_not_object() {
        assert!(!is_empty_condition_group(&json!("string")));
    }

    #[test]
    fn test_empty_group_value_number() {
        assert!(!is_empty_condition_group(&json!(42)));
    }

    #[test]
    fn test_empty_group_all_empty() {
        assert!(is_empty_condition_group(&json!({"all": []})));
    }

    #[test]
    fn test_empty_group_all_nonempty() {
        assert!(!is_empty_condition_group(&json!({"all": ["x"]})));
    }

    #[test]
    fn test_empty_group_any_empty() {
        assert!(is_empty_condition_group(&json!({"any": []})));
    }

    #[test]
    fn test_empty_group_any_nonempty() {
        assert!(!is_empty_condition_group(&json!({"any": ["x"]})));
    }

    #[test]
    fn test_empty_group_mode_all_empty() {
        assert!(is_empty_condition_group(
            &json!({"mode": "all", "conditions": []})
        ));
    }

    #[test]
    fn test_empty_group_mode_any_empty() {
        assert!(is_empty_condition_group(
            &json!({"mode": "any", "conditions": []})
        ));
    }

    #[test]
    fn test_empty_group_mode_nonempty() {
        assert!(!is_empty_condition_group(
            &json!({"mode": "all", "conditions": ["x"]})
        ));
    }

    #[test]
    fn test_empty_group_mode_invalid_value() {
        assert!(!is_empty_condition_group(
            &json!({"mode": 42, "conditions": []})
        ));
    }

    #[test]
    fn test_empty_group_mode_unknown() {
        assert!(!is_empty_condition_group(
            &json!({"mode": "bogus", "conditions": []})
        ));
    }

    // -----------------------------------------------------------------------
    // eval_condition_node — depth guard
    // -----------------------------------------------------------------------
    #[test]
    fn test_eval_depth_limit_string() {
        let r = eval_condition_node(&json!("x"), None, 999);
        assert!(!r.passed);
        assert_eq!(r.error.unwrap(), "nesting-too-deep");
        assert!(!r.has_required);
    }

    // -----------------------------------------------------------------------
    // eval_condition_node — string (leaf)
    // -----------------------------------------------------------------------
    #[test]
    fn test_eval_string_unknown_condition() {
        let r = eval_condition_node(&json!("nonexistent"), None, 0);
        assert!(!r.passed);
        assert!(r.has_required);
        assert!(r.error.unwrap().contains("unsupported-condition"));
    }

    // -----------------------------------------------------------------------
    // eval_condition_node — array
    // -----------------------------------------------------------------------
    #[test]
    fn test_eval_array_empty() {
        let r = eval_condition_node(&json!([]), None, 0);
        assert!(r.passed);
        assert!(r.has_required);
        assert!(r.error.is_none());
    }

    #[test]
    fn test_eval_array_mixed() {
        let r = eval_condition_node(&json!(["nonexistent_a"]), None, 0);
        assert!(!r.passed);
        assert!(r.has_required);
    }

    // -----------------------------------------------------------------------
    // eval_condition_node — object { "all": … }
    // -----------------------------------------------------------------------
    #[test]
    fn test_eval_object_all_empty() {
        let r = eval_condition_node(&json!({"all": []}), None, 0);
        assert!(r.passed);
    }

    #[test]
    fn test_eval_object_all_invalid_type() {
        let r = eval_condition_node(&json!({"all": 42}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
        assert_eq!(r.error.unwrap(), "invalid-all-list");
    }

    // -----------------------------------------------------------------------
    // eval_condition_node — object { "any": … }
    // -----------------------------------------------------------------------
    #[test]
    fn test_eval_object_any_empty() {
        let r = eval_condition_node(&json!({"any": []}), None, 0);
        assert!(r.passed);
    }

    #[test]
    fn test_eval_object_any_invalid_type() {
        let r = eval_condition_node(&json!({"any": 42}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
        assert_eq!(r.error.unwrap(), "invalid-any-list");
    }

    // -----------------------------------------------------------------------
    // eval_condition_node — object { "mode": …, "conditions": … }
    // -----------------------------------------------------------------------
    #[test]
    fn test_eval_object_mode_all_empty() {
        let r = eval_condition_node(&json!({"mode": "all", "conditions": []}), None, 0);
        assert!(r.passed);
    }

    #[test]
    fn test_eval_object_mode_any_empty() {
        let r = eval_condition_node(&json!({"mode": "any", "conditions": []}), None, 0);
        assert!(r.passed);
    }

    #[test]
    fn test_eval_object_mode_not_a_string() {
        let r = eval_condition_node(&json!({"mode": 42, "conditions": []}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
        assert_eq!(r.error.unwrap(), "invalid-mode-type");
    }

    #[test]
    fn test_eval_object_mode_unsupported() {
        let r = eval_condition_node(&json!({"mode": "maybe", "conditions": []}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
        assert!(r.error.unwrap().contains("unsupported-mode"));
    }

    #[test]
    fn test_eval_object_mode_missing_conditions() {
        let r = eval_condition_node(&json!({"mode": "all"}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
        assert_eq!(r.error.unwrap(), "missing-conditions");
    }

    #[test]
    fn test_eval_object_mode_conditions_not_list() {
        let r = eval_condition_node(&json!({"mode": "all", "conditions": 99}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
        assert_eq!(r.error.unwrap(), "conditions-not-list");
    }

    // -----------------------------------------------------------------------
    // eval_condition_node — object { "name": …, "required": … }
    // -----------------------------------------------------------------------
    #[test]
    fn test_eval_object_missing_name() {
        let r = eval_condition_node(&json!({"foo": "bar"}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
        assert_eq!(r.error.unwrap(), "unsupported-object");
    }

    #[test]
    fn test_eval_object_name_not_string() {
        let r = eval_condition_node(&json!({"name": 42}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
        assert_eq!(r.error.unwrap(), "unsupported-object");
    }

    #[test]
    fn test_eval_object_required_not_bool() {
        let r = eval_condition_node(&json!({"name": "x", "required": 99}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
        assert_eq!(r.error.unwrap(), "required-not-bool");
    }

    #[test]
    fn test_eval_object_optional_cond_unknown() {
        let r = eval_condition_node(&json!({"name": "unknown_cond", "required": false}), None, 0);
        assert!(!r.passed);
        assert!(!r.has_required);
    }

    // -----------------------------------------------------------------------
    // eval_condition_list — mode "all"
    // -----------------------------------------------------------------------
    #[test]
    fn test_eval_list_all_empty() {
        let r = eval_condition_list("all", &[], None, 0);
        assert!(r.passed);
        assert!(!r.has_required);
    }

    // -----------------------------------------------------------------------
    // fnmatch — exact
    // -----------------------------------------------------------------------
    #[test]
    fn test_fnmatch_exact_match() {
        assert!(fnmatch::fnmatch("hello", "hello").unwrap());
    }

    #[test]
    fn test_fnmatch_exact_mismatch() {
        assert!(!fnmatch::fnmatch("hello", "world").unwrap());
    }

    // -----------------------------------------------------------------------
    // fnmatch — *
    // -----------------------------------------------------------------------
    #[test]
    fn test_fnmatch_wildcard_prefix() {
        assert!(fnmatch::fnmatch("hello", "h*").unwrap());
    }

    #[test]
    fn test_fnmatch_wildcard_suffix() {
        assert!(fnmatch::fnmatch("hello", "*o").unwrap());
    }

    #[test]
    fn test_fnmatch_wildcard_any() {
        assert!(fnmatch::fnmatch("hello", "*").unwrap());
    }

    #[test]
    fn test_fnmatch_wildcard_empty_string() {
        assert!(fnmatch::fnmatch("", "*").unwrap());
    }

    #[test]
    fn test_fnmatch_wildcard_infix() {
        assert!(fnmatch::fnmatch("hello", "h*o").unwrap());
    }

    #[test]
    fn test_fnmatch_wildcard_no_match() {
        assert!(!fnmatch::fnmatch("hello", "h*x").unwrap());
    }

    // -----------------------------------------------------------------------
    // fnmatch — ?
    // -----------------------------------------------------------------------
    #[test]
    fn test_fnmatch_qmark_single() {
        assert!(fnmatch::fnmatch("hello", "h?llo").unwrap());
    }

    #[test]
    fn test_fnmatch_qmark_all() {
        assert!(fnmatch::fnmatch("hello", "?????").unwrap());
    }

    #[test]
    fn test_fnmatch_qmark_too_short() {
        assert!(!fnmatch::fnmatch("hello", "????").unwrap());
    }

    #[test]
    fn test_fnmatch_qmark_too_few() {
        // 'h?' matches 2 chars, 'hi' is exactly 2 -> match
        assert!(fnmatch::fnmatch("hi", "h?").unwrap());
        // but 'h' alone is too short
        assert!(!fnmatch::fnmatch("h", "h?").unwrap());
    }

    // -----------------------------------------------------------------------
    // fnmatch — escape
    // -----------------------------------------------------------------------
    #[test]
    fn test_fnmatch_escape_qmark() {
        assert!(fnmatch::fnmatch("hello?", r"hello\?").unwrap());
    }

    #[test]
    fn test_fnmatch_escape_star() {
        assert!(fnmatch::fnmatch("hello*", r"hello\*").unwrap());
    }

    // -----------------------------------------------------------------------
    // fnmatch — [...]
    // -----------------------------------------------------------------------
    #[test]
    fn test_fnmatch_char_class_range() {
        assert!(fnmatch::fnmatch("hello", "[a-z]ello").unwrap());
    }

    #[test]
    fn test_fnmatch_char_class_upper() {
        assert!(fnmatch::fnmatch("Hello", "[A-Z]ello").unwrap());
    }

    #[test]
    fn test_fnmatch_char_class_no_match() {
        assert!(!fnmatch::fnmatch("hello", "[A-Z]ello").unwrap());
    }

    #[test]
    fn test_fnmatch_unclosed_bracket() {
        assert!(!fnmatch::fnmatch("hello", "h[ello").unwrap());
    }

    #[test]
    fn test_fnmatch_empty_class() {
        assert!(!fnmatch::fnmatch("h", "h[]").unwrap());
    }

    #[test]
    fn test_fnmatch_char_class_escaped_dash() {
        // [a\-c] matches 'a', '-', or 'c'
        assert!(fnmatch::fnmatch("-", "[a\\-c]").unwrap());
        assert!(fnmatch::fnmatch("a", "[a\\-c]").unwrap());
        assert!(fnmatch::fnmatch("c", "[a\\-c]").unwrap());
        assert!(!fnmatch::fnmatch("b", "[a\\-c]").unwrap());
    }

    // -----------------------------------------------------------------------
    // evaluate — no rules
    // -----------------------------------------------------------------------
    #[test]
    fn test_evaluate_no_rules_allowed() {
        let b = PolicyWrapper {
            schema_version: 1,
            required_conditions: vec![],
            commands: vec![],
        };
        let r = evaluate(&b, "git push", None);
        assert_eq!(r.decision, "allow");
        assert!(!r.matched);
    }

    // -----------------------------------------------------------------------
    // evaluate — exact allow
    // -----------------------------------------------------------------------
    #[test]
    fn test_evaluate_exact_allow() {
        let b = PolicyWrapper {
            schema_version: 1,
            required_conditions: vec![],
            commands: vec![Rule {
                id: "r1".into(),
                source: "test".into(),
                action: "allow".into(),
                on_mismatch: None,
                matcher: "exact".into(),
                pattern: "git push".into(),
                normalized_pattern: "git push".into(),
                conditions: json!([]),
                platform_action: String::new(),
                shell_entry: String::new(),
                bash_entry: String::new(),
            }],
        };
        let r = evaluate(&b, "git push", None);
        assert_eq!(r.decision, "allow");
        assert!(r.matched);
        assert_eq!(r.rule_id, "r1");
    }

    // -----------------------------------------------------------------------
    // evaluate — deny beats allow
    // -----------------------------------------------------------------------
    #[test]
    fn test_evaluate_deny_overrides_allow() {
        let b = PolicyWrapper {
            schema_version: 1,
            required_conditions: vec![],
            commands: vec![
                Rule {
                    id: "allow_all".into(),
                    source: "test".into(),
                    action: "allow".into(),
                    on_mismatch: None,
                    matcher: "prefix".into(),
                    pattern: "git".into(),
                    normalized_pattern: "git".into(),
                    conditions: json!([]),
                    platform_action: String::new(),
                    shell_entry: String::new(),
                    bash_entry: String::new(),
                },
                Rule {
                    id: "deny_force".into(),
                    source: "test".into(),
                    action: "deny".into(),
                    on_mismatch: None,
                    matcher: "exact".into(),
                    pattern: "git push -f".into(),
                    normalized_pattern: "git push -f".into(),
                    conditions: json!([]),
                    platform_action: String::new(),
                    shell_entry: String::new(),
                    bash_entry: String::new(),
                },
            ],
        };
        let r = evaluate(&b, "git push -f", None);
        assert_eq!(r.decision, "deny");
        assert_eq!(r.rule_id, "deny_force");
    }

    // -----------------------------------------------------------------------
    // evaluate — rule mismatch (no matching rule)
    // -----------------------------------------------------------------------
    #[test]
    fn test_evaluate_no_matching_rule() {
        let b = PolicyWrapper {
            schema_version: 1,
            required_conditions: vec![],
            commands: vec![make_rule("r1", "exact", "git push")],
        };
        let r = evaluate(&b, "hg pull", None);
        assert_eq!(r.decision, "allow");
        assert!(!r.matched);
    }

    // -----------------------------------------------------------------------
    // evaluate — condition error produces "request"
    // -----------------------------------------------------------------------
    #[test]
    fn test_evaluate_condition_error_requests() {
        let b = PolicyWrapper {
            schema_version: 1,
            required_conditions: vec![],
            commands: vec![Rule {
                id: "r1".into(),
                source: "test".into(),
                action: "allow".into(),
                on_mismatch: Some("deny".into()),
                matcher: "exact".into(),
                pattern: "risky".into(),
                normalized_pattern: "risky".into(),
                conditions: json!("unknown_condition_xyz"),
                platform_action: String::new(),
                shell_entry: String::new(),
                bash_entry: String::new(),
            }],
        };
        let r = evaluate(&b, "risky", None);
        assert_eq!(r.decision, "request");
        assert!(r.matched);
        assert!(r.error.contains("unsupported-condition"));
    }
}
