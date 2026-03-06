## Zig wrapper (planned)

The protocol contract now has a runnable Zig implementation:

1. Read `policy_wrapper` JSON from `--bundle`
2. Evaluate ordered `commands` using same match + condition logic
3. Emit `allow|request|deny`

Build and run:

```bash
cd policy-contract/wrappers/zig
zig build
./zig-out/bin/policy-wrapper \
  --bundle /tmp/policy-wrapper-rules.json \
  --command "git checkout main" \
  --cwd /path/to/repo \
  --json
```

Behavior:

- Reads schema-aligned JSON from `--bundle`
- Evaluates ordered rules with `exact`, `prefix`, `glob`, and condition groups
- Emits `allow` when no conditional rule matches
- Returns `request` when condition checks fail unexpectedly
