import json
from dataclasses import dataclass

from pydantic import BaseModel

from novel_os.prompts.contracts import canonical, digest
from novel_os.prompts.registry import unique_object


class OutputFormatError(ValueError):
    pass


@dataclass(frozen=True)
class OutputContract:
    schema_id: str
    version: int
    model: type[BaseModel]
    schema_json: str

    @property
    def schema_hash(self):
        return digest(self.schema_json)

    def parse(self, raw: str):
        if not isinstance(raw, str) or len(raw) > 150_000:
            raise OutputFormatError
        try:
            body = json.loads(raw, object_pairs_hook=unique_object)
        except (ValueError, RecursionError):
            raise OutputFormatError from None
        return self.model.model_validate(body)


class OutputContractGenerator:
    @staticmethod
    def generate(schema_id: str, version: int, model: type[BaseModel]) -> OutputContract:
        return OutputContract(schema_id, version, model, canonical(model.model_json_schema()))
