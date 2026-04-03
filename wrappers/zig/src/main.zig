const std = @import("std");

const Rule = struct {
    id: []const u8,
    source: []const u8,
    action: []const u8,
    on_mismatch: ?[]const u8 = null,
    matcher: []const u8,
    pattern: []const u8,
    normalized_pattern: []const u8,
    conditions: std.json.Value,
    platform_action: []const u8,
    shell_entry: []const u8,
    bash_entry: []const u8,
};

const PolicyWrapper = struct {
    schema_version: u32,
    required_conditions: []const []const u8 = &EMPTY_REASONS,
    commands: []const Rule,
};

const EvalResult = struct {
    command: []const u8,
    decision: []const u8,
    matched: bool,
    rule_id: []const u8 = "",
    rule_source: []const u8 = "",
    has_required: bool = false,
    condition_passed: bool,
    condition_reasons: []const []const u8 = &EMPTY_REASONS,
    @"error": []const u8 = "",
};

const ConditionEval = struct {
    passed: bool,
    has_required: bool,
    reasons: []const []const u8,
    @"error": ?[]const u8 = null,
};

const MAX_CONDITION_DEPTH = 64;

const EMPTY_REASONS = [_][]const u8{};

fn cloneReasonList(
    allocator: std.mem.Allocator,
    reason: []const u8,
) ![]const []const u8 {
    var reasons = try allocator.alloc([]const u8, 1);
    reasons[0] = try allocator.dupe(u8, reason);
    return reasons;
}

fn normalizeErrorName(
    allocator: std.mem.Allocator,
    raw_name: []const u8,
) ![]const u8 {
    var output = try allocator.alloc(u8, raw_name.len * 2);
    var out_len: usize = 0;
    var seen = false;

    for (raw_name, 0..) |ch, i| {
        if (i > 0 and std.ascii.isUpper(ch)) {
            output[out_len] = '-';
            out_len += 1;
        } else if (ch == '_') {
            output[out_len] = '-';
            out_len += 1;
        }
        if (ch == '_') {
            continue;
        }
        output[out_len] = std.ascii.toLower(ch);
        out_len += 1;
        seen = true;
    }

    if (!seen) {
        return "";
    }

    return output[0..out_len];
}

fn normalizeCommand(allocator: std.mem.Allocator, command: []const u8) ![]const u8 {
    if (command.len == 0) return "";
    var out = try allocator.alloc(u8, command.len);
    var out_len: usize = 0;
    var in_whitespace = true;
    for (command) |c| {
        if (std.ascii.isWhitespace(c)) {
            if (!in_whitespace and out_len < out.len) {
                out[out_len] = ' ';
                out_len += 1;
            }
            in_whitespace = true;
            continue;
        }
        out[out_len] = c;
        out_len += 1;
        in_whitespace = false;
    }
    if (out_len > 0 and out[out_len - 1] == ' ') {
        out_len -= 1;
    }
    return out[0..out_len];
}

fn runGit(cwd: ?[]const u8, args: []const []const u8, allocator: std.mem.Allocator) ![]u8 {
    var child = std.process.Child.init(args, allocator);
    child.stdin_behavior = .Ignore;
    child.stdout_behavior = .Pipe;
    child.stderr_behavior = .Pipe;
    
    // POSIX chdir requires a null-terminated path.
    if (cwd) |dir| {
        if (dir.len > 0) {
            const cwd_z = try allocator.dupeZ(u8, dir);
            defer allocator.free(cwd_z);
            child.cwd = cwd_z;
            try child.spawn();
        } else {
            try child.spawn();
        }
    } else {
        try child.spawn();
    }

    const stdout = try child.stdout.?.readToEndAlloc(allocator, 1024 * 1024);
    const stderr = try child.stderr.?.readToEndAlloc(allocator, 1024 * 1024);
    defer allocator.free(stderr);
    
    const term = try child.wait();
    if (term != .Exited or term.Exited != 0) {
        if (stderr.len > 0) {
            std.log.err("git failed: {s}", .{stderr});
        }
        return error.GitFailed;
    }
    return stdout;
}

fn evalCondition(name: []const u8, cwd: ?[]const u8, allocator: std.mem.Allocator) !bool {
    if (std.mem.eql(u8, name, "git_is_worktree")) {
        const out = try runGit(cwd, &[_][]const u8{ "git", "rev-parse", "--is-inside-work-tree" }, allocator);
        defer allocator.free(out);
        return std.mem.eql(u8, std.mem.trim(u8, out, "\n"), "true");
    }
    if (std.mem.eql(u8, name, "git_clean_worktree")) {
        const out = try runGit(cwd, &[_][]const u8{ "git", "status", "--porcelain" }, allocator);
        defer allocator.free(out);
        return out.len == 0;
    }
    if (std.mem.eql(u8, name, "git_synced_to_upstream")) {
        const out_upstream = try runGit(cwd, &[_][]const u8{ "git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}" }, allocator);
        allocator.free(out_upstream);
        
        const counts = try runGit(
            cwd,
            &[_][]const u8{ "git", "rev-list", "--left-right", "--count", "@{u}...HEAD" },
            allocator,
        );
        defer allocator.free(counts);
        var it = std.mem.tokenizeAny(u8, counts, " \t\r\n");
        const behind = it.next() orelse return error.GitBehindNotFound;
        const ahead = it.next() orelse return error.GitAheadNotFound;
        if (it.next() != null) {
            return false;
        }
        _ = std.fmt.parseInt(i64, behind, 10) catch return error.GitBehindParseError;
        _ = std.fmt.parseInt(i64, ahead, 10) catch return error.GitAheadParseError;
        return std.mem.eql(u8, behind, "0") and std.mem.eql(u8, ahead, "0");
    }
    return error.UnsupportedCondition;
}

fn evalConditionList(
    mode: []const u8,
    conditions: []const std.json.Value,
    cwd: ?[]const u8,
    depth: usize,
    allocator: std.mem.Allocator,
) std.mem.Allocator.Error!ConditionEval {
    var reasons = std.array_list.Managed([]const u8).init(allocator);
    if (conditions.len == 0) {
        return ConditionEval{
            .passed = true,
            .has_required = false,
            .reasons = &EMPTY_REASONS,
            .@"error" = null,
        };
    }

    var pass_required = false;
    var pass_optional = false;
    var has_required = false;
    var first_error: ?[]const u8 = null;

    for (conditions) |condition| {
        const child = try evalConditionNode(condition, cwd, depth + 1, allocator);
        var child_required = child.has_required;
        if (!child_required) {
            child_required = isEmptyConditionContainer(condition);
        }
        try reasons.appendSlice(child.reasons);

        if (child.@"error") |err| {
            if (first_error == null) {
                first_error = err;
            }
        }

        if (child_required) {
            has_required = true;
            if (!child.passed and std.mem.eql(u8, mode, "all")) {
                return ConditionEval{
                    .passed = false,
                    .has_required = has_required,
                    .reasons = try reasons.toOwnedSlice(),
                    .@"error" = first_error,
                };
            }
        }

        if (child.passed) {
            if (child_required) {
                pass_required = true;
            } else {
                pass_optional = true;
            }
        }

    }

    if (std.mem.eql(u8, mode, "any")) {
        const passed = pass_required or (!has_required and pass_optional);
        return ConditionEval{
            .passed = passed,
            .has_required = has_required,
            .reasons = try reasons.toOwnedSlice(),
            .@"error" = first_error,
        };
    }

    return ConditionEval{
        .passed = true,
        .has_required = has_required,
        .reasons = try reasons.toOwnedSlice(),
        .@"error" = first_error,
    };
}

fn isEmptyConditionContainer(value: std.json.Value) bool {
    if (value != .object) {
        return false;
    }
    const object = value.object;

    if (object.get("all")) |raw_all| {
        if (raw_all != .array) return false;
        return raw_all.array.items.len == 0;
    }

    if (object.get("any")) |raw_any| {
        if (raw_any != .array) return false;
        return raw_any.array.items.len == 0;
    }

    if (object.get("mode")) |raw_mode| {
        if (raw_mode != .string) return false;
        const mode = raw_mode.string;
        if (!std.mem.eql(u8, mode, "all") and !std.mem.eql(u8, mode, "any")) {
            return false;
        }
        const raw_conditions = object.get("conditions") orelse return false;
        if (raw_conditions != .array) return false;
        return raw_conditions.array.items.len == 0;
    }

    return false;
}

fn evalConditionNode(
    value: std.json.Value,
    cwd: ?[]const u8,
    depth: usize,
    allocator: std.mem.Allocator,
) std.mem.Allocator.Error!ConditionEval {
    if (depth > MAX_CONDITION_DEPTH) {
        return ConditionEval{
            .passed = false,
            .has_required = false,
            .reasons = try cloneReasonList(allocator, "condition depth limit exceeded"),
            .@"error" = "nesting-too-deep",
        };
    }

    if (value == .string) {
        const name = value.string;
        const ok = evalCondition(name, cwd, allocator) catch |err| {
            const reason = try std.fmt.allocPrint(allocator, "{s}: {s}", .{ name, @errorName(err) });
            const detail = try normalizeErrorName(allocator, @errorName(err));
            const reasons = try cloneReasonList(allocator, reason);
            return ConditionEval{
                .passed = false,
                .has_required = true,
                .reasons = reasons,
                .@"error" = detail,
            };
        };
        const reasons = try cloneReasonList(allocator, name);
        return ConditionEval{
            .passed = ok,
            .has_required = true,
            .reasons = reasons,
            .@"error" = null,
        };
    }

    if (value == .array) {
        const result = try evalConditionList("all", value.array.items, cwd, depth, allocator);
        return ConditionEval{
            .passed = result.passed,
            .has_required = true,
            .reasons = result.reasons,
            .@"error" = result.@"error",
        };
    }

    if (value == .object) {
        const object = value.object;
        if (object.get("all")) |raw_all| {
            if (raw_all != .array) {
                return ConditionEval{
                    .passed = false,
                    .has_required = false,
                    .reasons = try cloneReasonList(allocator, "invalid condition list for all"),
                    .@"error" = "invalid-all-list",
                };
            }
            const result = try evalConditionList("all", raw_all.array.items, cwd, depth, allocator);
            return result;
        }

        if (object.get("any")) |raw_any| {
            if (raw_any != .array) {
                return ConditionEval{
                    .passed = false,
                    .has_required = false,
                    .reasons = try cloneReasonList(allocator, "invalid condition list for any"),
                    .@"error" = "invalid-any-list",
                };
            }
            const result = try evalConditionList("any", raw_any.array.items, cwd, depth, allocator);
            return result;
        }

        if (object.get("mode")) |raw_mode| {
            if (raw_mode != .string) {
                return ConditionEval{
                    .passed = false,
                    .has_required = false,
                    .reasons = try cloneReasonList(allocator, "invalid condition mode"),
                    .@"error" = "invalid-mode-type",
                };
            }
            const mode = raw_mode.string;
            if (!std.mem.eql(u8, mode, "all") and !std.mem.eql(u8, mode, "any")) {
                const detail = try std.fmt.allocPrint(allocator, "unsupported-mode:{s}", .{mode});
                return ConditionEval{
                    .passed = false,
                    .has_required = false,
                    .reasons = try cloneReasonList(allocator, detail),
                    .@"error" = detail,
                };
            }

            const raw_conditions = object.get("conditions") orelse {
                return ConditionEval{
                    .passed = false,
                    .has_required = false,
                    .reasons = try cloneReasonList(
                        allocator,
                        "condition mode missing conditions",
                    ),
                    .@"error" = "missing-conditions",
                };
            };
            if (raw_conditions != .array) {
                return ConditionEval{
                    .passed = false,
                    .has_required = false,
                    .reasons = try cloneReasonList(
                        allocator,
                        "condition mode conditions must be list",
                    ),
                    .@"error" = "conditions-not-list",
                };
            }
            const result = try evalConditionList(mode, raw_conditions.array.items, cwd, depth, allocator);
            return result;
        }

        const raw_name = object.get("name") orelse {
            return ConditionEval{
                .passed = false,
                .has_required = false,
                .reasons = try cloneReasonList(allocator, "unsupported condition object"),
                .@"error" = "unsupported-object",
            };
        };
        if (raw_name != .string) {
            return ConditionEval{
                .passed = false,
                .has_required = false,
                .reasons = try cloneReasonList(allocator, "invalid condition name"),
                .@"error" = "invalid-name-type",
            };
        }
        const name = raw_name.string;

        var required = true;
        if (object.get("required")) |raw_required| {
            if (raw_required != .bool) {
                return ConditionEval{
                    .passed = false,
                    .has_required = false,
                    .reasons = try cloneReasonList(allocator, "condition.required must be boolean"),
                    .@"error" = "required-not-bool",
                };
            }
            required = raw_required.bool;
        }

        const ok = evalCondition(name, cwd, allocator) catch |err| {
            const reason = try std.fmt.allocPrint(allocator, "{s}: {s}", .{ name, @errorName(err) });
            const detail = try normalizeErrorName(allocator, @errorName(err));
            const reasons = try cloneReasonList(allocator, reason);
            return ConditionEval{
                .passed = false,
                .has_required = required,
                .reasons = reasons,
                .@"error" = detail,
            };
        };
        const reasons = try cloneReasonList(allocator, name);
        return ConditionEval{
            .passed = ok,
            .has_required = required,
            .reasons = reasons,
            .@"error" = null,
        };
    }

    return ConditionEval{
        .passed = false,
        .has_required = false,
        .reasons = try cloneReasonList(allocator, "unsupported condition type"),
        .@"error" = "unsupported-type",
    };
}

fn decisionRank(decision: []const u8) u8 {
    if (std.mem.eql(u8, decision, "deny")) return 3;
    if (std.mem.eql(u8, decision, "request")) return 2;
    if (std.mem.eql(u8, decision, "allow")) return 1;
    return 0;
}

fn globMatch(pattern: []const u8, text: []const u8) bool {
    return globRec(pattern, 0, text, 0);
}

fn globClassMatch(ch: u8, class: []const u8) bool {
    if (class.len == 0) {
        return false;
    }

    var idx: usize = 0;
    var found = false;
    while (idx < class.len) {
        if (class[idx] == '\\') {
            if (idx + 1 >= class.len) {
                return false;
            }
            if (ch == class[idx + 1]) {
                found = true;
            }
            idx += 2;
            continue;
        }

        if (idx + 2 < class.len and class[idx + 1] == '-') {
            const start = class[idx];
            const end = class[idx + 2];
            if (ch >= start and ch <= end) {
                found = true;
            }
            idx += 3;
            continue;
        }

        if (ch == class[idx]) {
            found = true;
        }
        idx += 1;
    }
    return found;
}

fn globRec(pat: []const u8, pi: usize, text: []const u8, ti: usize) bool {
    if (pi == pat.len) return ti == text.len;
    return switch (pat[pi]) {
        '*' => {
            var i = ti;
            while (i <= text.len) : (i += 1) {
                if (globRec(pat, pi + 1, text, i)) return true;
            }
            return false;
        },
        '?' => {
            if (ti >= text.len) return false;
            return globRec(pat, pi + 1, text, ti + 1);
        },
        '\\' => {
            if (pi + 1 >= pat.len or ti >= text.len) return false;
            return pat[pi + 1] == text[ti] and globRec(pat, pi + 2, text, ti + 1);
        },
        '[' => {
            var closing: usize = pi + 1;
            while (closing < pat.len and pat[closing] != ']') {
                closing += 1;
            }
            if (closing >= pat.len) return false;
            if (ti >= text.len) return false;

            const class = pat[pi + 1 .. closing];

            const matched = globClassMatch(text[ti], class);
            if (!matched) return false;
            return globRec(pat, closing + 1, text, ti + 1);
        },
        else => {
            if (ti >= text.len) return false;
            return pat[pi] == text[ti] and globRec(pat, pi + 1, text, ti + 1);
        },
    };
}

fn matchesRule(rule: Rule, command: []const u8) bool {
    const pattern = rule.normalized_pattern;
    if (std.mem.eql(u8, rule.matcher, "exact")) return std.mem.eql(u8, command, pattern);
    if (std.mem.eql(u8, rule.matcher, "prefix")) return std.mem.startsWith(u8, command, pattern);
    return globMatch(pattern, command);
}

fn parseArgs(allocator: std.mem.Allocator) !struct {
    bundle: []const u8,
    command: []const u8,
    cwd: ?[]const u8,
    as_json: bool,
} {
    const args = try std.process.argsAlloc(allocator);

    var bundle: ?[]const u8 = null;
    var command: ?[]const u8 = null;
    var cwd: ?[]const u8 = null;
    var as_json = false;

    var idx: usize = 1;
    while (idx < args.len) {
        const arg = args[idx];
        if (std.mem.eql(u8, arg, "--bundle")) {
            idx += 1;
            if (idx >= args.len) return error.BadUsage;
            bundle = args[idx];
        } else if (std.mem.eql(u8, arg, "--command")) {
            idx += 1;
            if (idx >= args.len) return error.BadUsage;
            command = args[idx];
        } else if (std.mem.eql(u8, arg, "--cwd")) {
            idx += 1;
            if (idx >= args.len) return error.BadUsage;
            cwd = args[idx];
        } else if (std.mem.eql(u8, arg, "--json")) {
            as_json = true;
        } else {
            return error.BadUsage;
        }
        idx += 1;
    }

    const bundle_value = bundle orelse return error.BadUsage;
    const command_value = command orelse return error.BadUsage;
    const bundle_copy = try allocator.dupe(u8, bundle_value);
    const command_copy = try allocator.dupe(u8, command_value);
    const cwd_copy = if (cwd) |cwd_value| try allocator.dupe(u8, cwd_value) else null;

    return .{
        .bundle = bundle_copy,
        .command = command_copy,
        .cwd = cwd_copy,
        .as_json = as_json,
    };
}

fn printResult(
    result: EvalResult,
    as_json: bool,
    allocator: std.mem.Allocator,
) !void {
    const stdout = std.fs.File.stdout();
    if (!as_json) {
        var line_buf: [128]u8 = undefined;
        const line = try std.fmt.bufPrint(&line_buf, "{s}\n", .{result.decision});
        try stdout.writeAll(line);
        return;
    }

    const payload = .{
        .command = result.command,
        .decision = result.decision,
        .matched = result.matched,
        .rule_id = result.rule_id,
        .rule_source = result.rule_source,
        .has_required = result.has_required,
        .condition_passed = result.condition_passed,
        .condition_reasons = result.condition_reasons,
        .@"error" = result.@"error",
    };
    const payload_text = try std.json.Stringify.valueAlloc(allocator, payload, .{});
    defer allocator.free(payload_text);
    try stdout.writeAll(payload_text);
    try stdout.writeAll("\n");
}

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const opts = try parseArgs(allocator);
    defer allocator.free(opts.bundle);
    defer allocator.free(opts.command);
    defer if (opts.cwd) |cwd| allocator.free(cwd);

    const normalized = try normalizeCommand(allocator, opts.command);
    defer allocator.free(normalized);

    const bundle_bytes = try std.fs.cwd().readFileAlloc(allocator, opts.bundle, 4 * 1024 * 1024);
    defer allocator.free(bundle_bytes);

    const parsed = std.json.parseFromSliceLeaky(PolicyWrapper, allocator, bundle_bytes, .{}) catch {
        std.log.err("invalid bundle JSON: {s}", .{opts.bundle});
        std.process.exit(1);
    };
    const policy = parsed;

    var matched = false;
    var best_rank: u8 = 0;
    var best_decision: []const u8 = "allow";
    var best_error: []const u8 = "";
    var best_rule: ?Rule = null;
    var best_condition_passed = true;
    var best_has_required = false;
    var best_condition_reasons: []const []const u8 = &EMPTY_REASONS;

    for (policy.commands) |rule| {
        if (!matchesRule(rule, normalized)) continue;
        matched = true;

        const eval = evalConditionNode(rule.conditions, opts.cwd, 0, allocator) catch |err| {
            const rank = decisionRank("request");
            if (rank > best_rank) {
                best_rank = rank;
                best_decision = "request";
                best_error = try normalizeErrorName(allocator, @errorName(err));
                best_rule = rule;
                best_condition_passed = false;
                best_condition_reasons = &EMPTY_REASONS;
            }
            continue;
        };

        const cond_passed = eval.passed;
        const has_required = eval.has_required;
        const reasons = eval.reasons;
        const condition_error = eval.@"error";

        var decision: []const u8 = "allow";
        var condition_passed = cond_passed;
        var error_text: []const u8 = "";
        if (condition_error) |err| {
            decision = "request";
            condition_passed = false;
            error_text = err;
        } else if (cond_passed) {
            decision = rule.action;
        } else if (rule.on_mismatch) |fallback| {
            if (fallback.len > 0) {
                decision = fallback;
            } else {
                continue;
            }
        } else {
            continue;
        }

        const rank = decisionRank(decision);
        if (rank <= best_rank) {
            continue;
        }

        best_rank = rank;
        best_decision = decision;
        best_rule = rule;
        best_has_required = has_required;
        best_condition_passed = condition_passed;
        best_condition_reasons = reasons;
        best_error = error_text;
    }

    if (!matched) {
        try printResult(.{
            .command = normalized,
            .decision = "allow",
            .matched = false,
            .condition_passed = true,
            .has_required = false,
        }, opts.as_json, allocator);
        return;
    }

    if (best_rank == 0) {
        try printResult(.{
            .command = normalized,
            .decision = "allow",
            .matched = true,
            .condition_passed = true,
            .has_required = false,
            .condition_reasons = &EMPTY_REASONS,
        }, opts.as_json, allocator);
        return;
    }

    var rule_id: []const u8 = "";
    var rule_source: []const u8 = "";
    if (best_rule) |selected| {
        rule_id = selected.id;
        rule_source = selected.source;
    }

    try printResult(.{
        .command = normalized,
        .decision = best_decision,
        .matched = true,
        .rule_id = rule_id,
        .rule_source = rule_source,
        .condition_passed = best_condition_passed,
        .has_required = best_has_required,
        .condition_reasons = best_condition_reasons,
        .@"error" = best_error,
    }, opts.as_json, allocator);
}
