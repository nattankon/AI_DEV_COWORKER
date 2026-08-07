from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_SECRET_DIRECTORIES = {
    ".aws",
    ".azure",
    ".gnupg",
    ".kube",
    ".ssh",
}
_PRIVATE_KEY_NAMES = {
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
_PRIVATE_KEY_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
_CREDENTIAL_FILE_NAMES = {
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    # This app's own provider-key store (and its legacy name). The app loads these
    # directly via model_catalog, so blocking them here stops only the agent's
    # read/write tools from touching the user's API keys.
    "credentials.txt",
    "key.txt",
}
_ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template")


class SecretAccessError(PermissionError):
    pass


@dataclass(frozen=True)
class SecretDecision:
    allowed: bool
    reason: str = ""


class SecretGuard:
    def evaluate(self, path: str | Path) -> SecretDecision:
        candidate = Path(path)
        normalized_parts = tuple(_normalize_name(part) for part in candidate.parts if part not in {"", "."})
        if any(part in _SECRET_DIRECTORIES for part in normalized_parts):
            return SecretDecision(False, "credential store directory")

        name = _normalize_name(candidate.name)
        if name == ".env" or (name.startswith(".env.") and not name.endswith(_ENV_TEMPLATE_SUFFIXES)):
            return SecretDecision(False, "environment secret file")
        if name in _PRIVATE_KEY_NAMES or Path(name).suffix in _PRIVATE_KEY_SUFFIXES:
            return SecretDecision(False, "private key or certificate file")
        if name in _CREDENTIAL_FILE_NAMES:
            return SecretDecision(False, "credential file")
        return SecretDecision(True)

    def require_allowed(self, path: str | Path) -> None:
        decision = self.evaluate(path)
        if not decision.allowed:
            raise SecretAccessError(f"Secret access denied: {decision.reason}")


def _normalize_name(value: str) -> str:
    return value.split(":", 1)[0].rstrip(" .").casefold()
