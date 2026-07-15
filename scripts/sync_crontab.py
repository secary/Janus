import os
import re
import subprocess
import sys
import tempfile

from sqlalchemy import text

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from config.settings import get_engine  # noqa: E402


SYNC_COMMAND = "/app/.venv/bin/python /app/scripts/sync_crontab.py"
COMMAND_PREFIX = "/app/.venv/bin/python /app/"
OUTPUT_REDIRECT = ">> /proc/1/fd/1 2>&1"
CRON_FIELD_PATTERN = re.compile(r"^[0-9A-Za-z*/,\-]+$")


def normalize_cron_expression(value):
    return " ".join(str(value or "").strip().split())


def validate_cron_expression(value):
    expression = normalize_cron_expression(value)
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("cron expression must contain 5 fields")

    for field in fields:
        if not CRON_FIELD_PATTERN.fullmatch(field):
            raise ValueError(f"unsupported cron field: {field}")

    return expression


def validate_command(value):
    command = str(value or "").strip()
    if not command.startswith(COMMAND_PREFIX):
        raise ValueError("command must run a script under /app with the project virtualenv")
    if "\n" in command or "\r" in command:
        raise ValueError("command cannot contain line breaks")
    return command


def load_schedule_config():
    engine = get_engine()
    with engine.connect() as conn:
        return conn.execute(
            text(
                """
                SELECT job_key, job_name, cron_expression, `command`, enabled
                FROM schedule_config
                ORDER BY job_key ASC
                """
            )
        ).mappings().all()


def render_crontab(rows):
    lines = [
        "# Managed by Janus. Database table: schedule_config.",
        "SHELL=/bin/sh",
        "PATH=/app/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "",
        "# Refresh this crontab from schedule_config every minute.",
        f"* * * * * {SYNC_COMMAND} {OUTPUT_REDIRECT}",
    ]

    for row in rows:
        job_key = row["job_key"]
        job_name = row["job_name"]
        if not bool(row["enabled"]):
            lines.extend(["", f"# Disabled: {job_key} - {job_name}"])
            continue

        try:
            expression = validate_cron_expression(row["cron_expression"])
            command = validate_command(row["command"])
        except ValueError as exc:
            lines.extend(["", f"# Skipped invalid job {job_key}: {exc}"])
            continue

        lines.extend(["", f"# {job_key} - {job_name}", f"{expression} {command} {OUTPUT_REDIRECT}"])

    return "\n".join(lines) + "\n"


def current_crontab():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout


def install_crontab(content):
    if current_crontab().strip() == content.strip():
        print("Janus crontab is already up to date.")
        return

    path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as file:
            file.write(content)
            path = file.name
        subprocess.run(["crontab", path], check=True)
        print("Janus crontab refreshed from schedule_config.")
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def main():
    rows = load_schedule_config()
    install_crontab(render_crontab(rows))


if __name__ == "__main__":
    main()
