#!/usr/bin/env python3
"""
OpenClaw skill script — calls the Paraguay Startup Validator REST bridge.
Usage: python3 validate_idea.py --idea "tu idea aqui" [--depth quick|deep]
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser(description="Validate a startup idea against Paraguayan market data")
    parser.add_argument("--idea", required=True, help="Startup idea to validate (in Spanish)")
    parser.add_argument("--depth", default="deep", choices=["quick", "deep"],
                        help="quick=2 sources (~2s), deep=4 sources (~5s)")
    args = parser.parse_args()

    base_url = os.getenv("VALIDATOR_URL", "http://localhost:8001")
    url = f"{base_url}/validate"

    payload = json.dumps({"idea": args.idea, "depth": args.depth}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(json.dumps({
            "error": f"No se pudo conectar al validador en {base_url}. "
                     f"Asegurate de que el backend esté corriendo: "
                     f"uvicorn rest_bridge:app --port 8001. Detalle: {e}"
        }), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
