import json
import logging
from typing import Any


logger = logging.getLogger(__name__)


def dump_telegram_model(model: Any) -> dict | None:
    if model is None:
        return None

    if hasattr(model, "model_dump_json"):
        try:
            return json.loads(model.model_dump_json(exclude_none=False, by_alias=True))
        except (TypeError, ValueError):
            logger.exception("Failed to serialize Telegram model via model_dump_json")

    if hasattr(model, "model_dump"):
        try:
            return model.model_dump(mode="json", exclude_none=False, by_alias=True)
        except TypeError:
            try:
                return model.model_dump(exclude_none=False)
            except TypeError:
                return model.model_dump()

    return None
