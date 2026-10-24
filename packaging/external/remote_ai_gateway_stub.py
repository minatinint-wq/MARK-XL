"""The creator's private remote AI account is intentionally not distributed."""


class RemoteAIError(ValueError):
    pass


def start_gateway() -> bool:
    return False


def ask_local(question: str, model: str = "") -> dict:
    raise RemoteAIError("IA remota privada indisponível nesta edição.")
