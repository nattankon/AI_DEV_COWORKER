# Cowork verification presets

Cowork can only run **allow-listed** verification commands — it never executes
arbitrary shell input from the model. Out of the box the presets are:

| Preset | Command |
| ------ | ------- |
| `python-tests` | `python -m unittest discover -s test -p test_*.py` |
| `frontend-tests` | `npm test` |
| `frontend-build` | `npm run build` |

## Adding your own (any language)

Drop a `.cowork/verify.json` file in the project root to add project-specific
presets. This is how you unlock verification for C, C++, Lua, Go, Rust, or any
other toolchain:

```json
{
  "presets": {
    "run":     { "argv": ["lua", "main.lua"], "timeout_seconds": 30 },
    "c-build": { "argv": ["gcc", "main.c", "-o", "main.exe"], "timeout_seconds": 60 }
  }
}
```

- `argv` is the exact command and arguments (no shell, no `&&`); it runs with the
  project root as the working directory.
- `timeout_seconds` is optional (defaults to 120).
- Your presets are merged over the defaults; a preset that reuses a default name
  overrides it.
- Invalid entries are ignored silently.

Every preset — default or project-defined — still goes through the same approval
gate before it runs, so a project config can never execute a command without your
say-so.
