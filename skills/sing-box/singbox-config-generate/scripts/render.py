#!/usr/bin/env python3
"""Render a template by replacing ${VAR} with values from the environment.

Usage: render.py TEMPLATE OUTPUT [--env-file secrets.env]

- Only ${UPPER_CASE} tokens are substituted; every other character is copied verbatim.
- Fails (exit 1) if any ${VAR} used by the template is unset or still a placeholder
  such as TODO_*, so a half-filled config can never be produced silently.
- The output file is created with mode 600 (it contains secrets).
"""
import os, re, sys

def load_env(path):
    env = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            env[k.strip()] = v
    return env

def main():
    args = sys.argv[1:]
    env = dict(os.environ)
    if "--env-file" in args:
        i = args.index("--env-file")
        env.update(load_env(args[i + 1]))
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    src, dst = args
    text = open(src, encoding="utf-8").read()
    missing = []
    def sub(m):
        name = m.group(1)
        val = env.get(name)
        if val is None or val == "" or val.startswith("TODO"):
            missing.append(name)
            return m.group(0)
        return val
    out = re.sub(r"\$\{([A-Z][A-Z0-9_]*)\}", sub, text)
    if missing:
        sys.exit("render.py: unset/placeholder variables: " + ", ".join(sorted(set(missing))))
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(out)
    os.chmod(dst, 0o600)
    print("rendered", dst)

if __name__ == "__main__":
    main()
