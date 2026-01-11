from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ts_iso(ts: int) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:
        return ""


def _format_alert(alert: dict[str, Any]) -> str:
    score = alert.get("score")
    notional = alert.get("notional")
    url = alert.get("url")
    trade = alert.get("trade") or {}
    market = alert.get("market") or {}
    title = trade.get("title") or market.get("question") or ""
    try:
        notional_str = f"${float(notional):,.2f}"
    except Exception:
        notional_str = str(notional)
    return f"- score={score} notional={notional_str} market={title} url={url}"


def _post_slack(webhook_url: str, text: str) -> None:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=20) as resp:
        resp.read()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--alerts-json", default="docs/alerts.json")
    p.add_argument("--max-items", type=int, default=10)
    p.add_argument("--webhook-url", default=os.environ.get("SLACK_WEBHOOK_URL", ""))
    p.add_argument("--send-on-empty", action="store_true")
    args = p.parse_args(argv)

    if not args.webhook_url:
        raise SystemExit("Missing --webhook-url or SLACK_WEBHOOK_URL")

    payload = _load_json(Path(args.alerts_json))
    alerts = payload.get("alerts") if isinstance(payload, dict) else None
    if not isinstance(alerts, list):
        alerts = []

    new_alerts = payload.get("new_alerts") if isinstance(payload, dict) else None
    try:
        new_alerts_int = int(new_alerts)
    except Exception:
        new_alerts_int = 0

    if not alerts and not args.send_on_empty:
        return 0
    if new_alerts_int <= 0 and not args.send_on_empty:
        return 0

    generated_at = _ts_iso(payload.get("generated_at", 0))
    repo = payload.get("repo") or os.environ.get("GITHUB_REPOSITORY", "")
    run_url = payload.get("workflow_run_url") or ""

    header = "Polymarket Watch update"
    if repo:
        header = f"{header} ({repo})"

    lines = [
        header,
        f"generated_at={generated_at} new_alerts={new_alerts_int} total_alerts={len(alerts)}",
    ]
    if run_url:
        lines.append(f"run_url={run_url}")

    for alert in alerts[: max(0, int(args.max_items))]:
        if not isinstance(alert, dict):
            continue
        lines.append(_format_alert(alert))

    _post_slack(args.webhook_url, "
".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
