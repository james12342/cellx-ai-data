from __future__ import annotations

import argparse
import os
import smtplib
import subprocess
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS_DIR = ROOT / "reports"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing email config: {name}. Set it in environment variables or .env.")
    return value


def latest_report_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ["us_sectors_*.csv", "us_leaders_*.csv"]:
        matches = sorted(REPORTS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            files.append(matches[0])
    return files


def latest_markdown() -> str:
    matches = sorted(REPORTS_DIR.glob("us_radar_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        return ""
    text = matches[0].read_text(encoding="utf-8", errors="replace")
    return text[:4000]


def run_radar(args: argparse.Namespace) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "us_stock_sector_radar.py"),
        "--top-sectors",
        str(args.top_sectors),
        "--leaders-per-sector",
        str(args.leaders_per_sector),
        "--period",
        args.period,
    ]
    if args.institution_file:
        cmd.extend(["--institution-file", args.institution_file])
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Running US stock radar...")
    subprocess.run(cmd, cwd=ROOT, check=True)


def send_email(subject: str, body: str, attachments: list[Path]) -> None:
    smtp_host = require_env("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
    smtp_from = os.environ.get("SMTP_FROM", smtp_username).strip()
    smtp_to = require_env("SMTP_TO")
    use_tls = os.environ.get("SMTP_USE_TLS", "true").strip().lower() not in {"0", "false", "no"}

    if not smtp_from:
        raise SystemExit("Missing email config: SMTP_FROM or SMTP_USERNAME.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = smtp_to
    message.set_content(body)

    for path in attachments:
        message.add_attachment(
            path.read_bytes(),
            maintype="text",
            subtype="csv",
            filename=path.name,
        )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as smtp:
        if use_tls:
            smtp.starttls()
        if smtp_username and smtp_password:
            smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Email sent to {smtp_to}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run US stock radar and email CSV reports.")
    parser.add_argument("--top-sectors", type=int, default=8)
    parser.add_argument("--leaders-per-sector", type=int, default=3)
    parser.add_argument("--period", default="3mo")
    parser.add_argument("--institution-file", default=None)
    parser.add_argument("--dry-run-email", action="store_true", help="Run radar but do not send email.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    run_radar(args)
    attachments = latest_report_files()
    if not attachments:
        raise SystemExit("Radar ran, but no CSV files were found to email.")

    body = (
        "US Stock Sector Radar finished.\n\n"
        "Attached CSV files:\n"
        + "\n".join(f"- {path.name}" for path in attachments)
        + "\n\nReport preview:\n\n"
        + latest_markdown()
    )
    subject = f"US Stock Sector Radar CSV - {datetime.now():%Y-%m-%d}"

    if args.dry_run_email:
        print("[dry-run] Email not sent. Attachments:")
        for path in attachments:
            print(f"- {path}")
        return

    send_email(subject, body, attachments)


if __name__ == "__main__":
    main()
