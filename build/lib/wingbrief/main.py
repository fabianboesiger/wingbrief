"""Kommandozeile: python -m wingbrief.main plan|climatology."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import ROOT, climatology, engine, extract, output, stac

log = logging.getLogger("wingbrief")


def cmd_plan(args) -> int:
    run = datetime.fromisoformat(args.run) if args.run else stac.latest_complete_run()
    if run is None:
        log.error("Kein vollständiger ICON-CH2-Lauf gefunden")
        return 1
    if run.tzinfo is None:
        run = run.replace(tzinfo=timezone.utc)
    state_file = Path(args.state) if args.state else None
    if state_file and state_file.exists() and not args.force:
        last = json.loads(state_file.read_text()).get("run")
        if last == run.isoformat():
            log.info("Lauf %s bereits verarbeitet", run)
            print("unchanged")
            return 0
    t0 = time.time()
    b = extract.build_bundle(run, Path(args.cache), quick=args.quick, with_ensemble=not args.no_ensemble)
    status, results, catalog = engine.run_all(b)
    out = Path(args.out)
    sizes = output.write(b, status, results, catalog, out)
    output.copy_site(out)
    log.info("Ausgabe: %s", {k: f"{v / 1e3:.0f} kB" for k, v in sizes.items() if k in ("index.json", "meta.json")})
    log.info("Detaildateien: %.0f kB gesamt", sum(v for k, v in sizes.items() if k.startswith("detail")) / 1e3)
    if args.archive:
        output.archive(Path(args.archive), b, out / "data" / "index.json")
    if state_file:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"run": run.isoformat(), "processed": datetime.now(timezone.utc).isoformat(),
                                          "seconds": round(time.time() - t0)}))
    print("updated")
    return 0


def cmd_climatology(args) -> int:
    climatology.write()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="wingbrief")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan", help="Prognose-Checks für den neuesten Lauf rechnen")
    pl.add_argument("--run", help="Lauf (ISO, UTC), Standard: neuester vollständiger")
    pl.add_argument("--out", default=str(ROOT / "public"))
    pl.add_argument("--cache", default=str(ROOT / "cache"))
    pl.add_argument("--state", help="state.json; Lauf überspringen, wenn bereits verarbeitet")
    pl.add_argument("--archive", help="Verzeichnis für das Archiv je Lauf")
    pl.add_argument("--quick", action="store_true", help="weniger Zeitschritte (Entwicklung)")
    pl.add_argument("--no-ensemble", action="store_true")
    pl.add_argument("--force", action="store_true")
    pl.set_defaults(fn=cmd_plan)
    cl = sub.add_parser("climatology", help="Stationsklimatologie neu berechnen")
    cl.set_defaults(fn=cmd_climatology)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
