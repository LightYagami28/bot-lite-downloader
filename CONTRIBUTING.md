# Contributing

BotLite Downloader is under active maintenance after a period of several
months without regular updates. Light is currently coordinating the renewal of
the codebase, dependency updates, Telegram WebApp hardening and documentation;
the original authors and all prior contributors remain part of the project
history.

## Before opening a pull request

```bash
python -m pip install -r requirements-dev.txt
python -W error::DeprecationWarning -m pytest -q
python -m ruff check .
python -m pip_audit -r requirements-dev.txt
```

Do not commit `.env`, Telegram sessions, cookie files, databases, downloaded
media or credentials. New WebApp endpoints must validate Telegram `initData`
server-side and admin routes must enforce `SUDO_USERS`.

Group support must remain opt-in, rate-limited and safe for shared chats. Do
not log message contents, cookies or bot tokens. Prefer small, reviewable
commits and add regression tests for security-sensitive behavior.

## Release checklist

1. Update the version and changelog.
2. Run tests, Ruff and dependency audit.
3. Review the Docker image as a non-root user.
4. Tag the release and publish only verified artifacts.
