"""Explicit operator-invoked Ed25519 SOFTWARE test key provisioning (NOT HSM)."""
import argparse
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge.receipts import public_key_id


def generate(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    private_path = directory / "issuer-private.pem"
    public_path = directory / "issuer-public.pem"
    trust_path = directory / "trust-store.json"
    if any(path.exists() for path in (private_path, public_path, trust_path)):
        raise FileExistsError("Refusing to overwrite existing keys or trust store")
    private = Ed25519PrivateKey.generate()
    private_bytes = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = private.public_key()
    pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(private_path, flags, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(private_bytes)
    public_path.write_text(pem, encoding="ascii")
    trust_path.write_text(json.dumps({public_key_id(public): pem}, indent=2) + "\n", encoding="utf-8")
    return {"private_key_path": str(private_path), "trust_store_path": str(trust_path), "key_id": public_key_id(public),
            "claim": "LOCAL_SOFTWARE_KEY_ONLY", "warning": "Keep the private key private; do not commit this directory"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--directory", default=".imcp")
    args = ap.parse_args()
    print(json.dumps(generate(Path(args.directory)), indent=2))


if __name__ == "__main__":
    main()
