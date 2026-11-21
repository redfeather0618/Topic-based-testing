"""python -m foi_screening.replay --snapshot PATH --output NEW_DIRECTORY"""
import argparse
import json
import sys

from .runner import run


def main():
    parser = argparse.ArgumentParser(description='Offline replay of five annotated procedural rules')
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        summary = run(args.snapshot, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Replay failed: {error}', file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
