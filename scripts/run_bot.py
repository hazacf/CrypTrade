#!/usr/bin/env python3
"""Run CrypTrade in paper or live mode.

    python scripts/run_bot.py --config config.yaml

Mode (paper/live) and exchange come from the config file. LIVE mode requires
EXCHANGE_API_KEY / EXCHANGE_API_SECRET in the environment and will refuse to
start without them.
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptrade.config import load_config  # noqa: E402
from cryptrade.trader import Trader  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = load_config(args.config)

    if cfg.get("mode") == "live":
        s = cfg.get("secrets", {})
        if not s.get("api_key") or not s.get("api_secret"):
            raise SystemExit(
                "LIVE mode needs EXCHANGE_API_KEY and EXCHANGE_API_SECRET. "
                "Set them in your environment (.env). Start with testnet: true."
            )
        confirm = input(
            "You are about to run in LIVE mode with real funds. "
            "Type 'I UNDERSTAND' to continue: "
        )
        if confirm.strip() != "I UNDERSTAND":
            raise SystemExit("Aborted.")

    Trader(cfg).run()


if __name__ == "__main__":
    main()
