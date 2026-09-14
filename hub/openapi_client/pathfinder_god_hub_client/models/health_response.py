# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from typing import Literal, cast






T = TypeVar("T", bound="HealthResponse")



@_attrs_define
class HealthResponse:
    """ 
        Attributes:
            version (str):
            ollama_model (str):
            status (Literal['ok'] | Unset):  Default: 'ok'.
            databases_found (list[str] | Unset):
     """

    version: str
    ollama_model: str
    status: Literal['ok'] | Unset = 'ok'
    databases_found: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        version = self.version

        ollama_model = self.ollama_model

        status = self.status

        databases_found: list[str] | Unset = UNSET
        if not isinstance(self.databases_found, Unset):
            databases_found = self.databases_found




        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "version": version,
            "ollama_model": ollama_model,
        })
        if status is not UNSET:
            field_dict["status"] = status
        if databases_found is not UNSET:
            field_dict["databases_found"] = databases_found

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        version = d.pop("version")

        ollama_model = d.pop("ollama_model")

        status = cast(Literal['ok'] | Unset , d.pop("status", UNSET))
        if status != 'ok'and not isinstance(status, Unset):
            raise ValueError(f"status must match const 'ok', got '{status}'")

        databases_found = cast(list[str], d.pop("databases_found", UNSET))


        health_response = cls(
            version=version,
            ollama_model=ollama_model,
            status=status,
            databases_found=databases_found,
        )


        health_response.additional_properties = d
        return health_response

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
