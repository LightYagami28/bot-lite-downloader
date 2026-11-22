# Troubleshooting

## Telegram connection or authentication issues

Check the bot token and Telegram client/session configuration against the
current setup instructions in the [README](../README.md). Do not share tokens, session files, or
browser cookies in logs or issue reports.

## Download failures

Confirm the requested source is supported by the current configured integrations
and inspect the application logs after removing credentials and personal data.
Reproduce with a small safe example before reporting.

## Dashboard does not start

Verify the configured address/port and environment values, then check the
current CI and Docker configuration. Avoid assuming historical values in
`SPEC.md` match the current runtime.