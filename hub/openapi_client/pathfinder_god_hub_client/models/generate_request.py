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

from ..models.generate_request_edition import GenerateRequestEdition
from ..types import UNSET, Unset






T = TypeVar("T", bound="GenerateRequest")



@_attrs_define
class GenerateRequest:
    """ 
        Attributes:
            prompt (str): What to create, e.g. 'a cunning goblin alchemist boss'.
            edition (GenerateRequestEdition | Unset):  Default: GenerateRequestEdition.BOTH.
     """

    prompt: str
    edition: GenerateRequestEdition | Unset = GenerateRequestEdition.BOTH
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        prompt = self.prompt

        edition: str | Unset = UNSET
        if not isinstance(self.edition, Unset):
            edition = self.edition.value



        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "prompt": prompt,
        })
        if edition is not UNSET:
            field_dict["edition"] = edition

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        prompt = d.pop("prompt")

        _edition = d.pop("edition", UNSET)
        edition: GenerateRequestEdition | Unset
        if isinstance(_edition,  Unset):
            edition = UNSET
        else:
            edition = GenerateRequestEdition(_edition)




        generate_request = cls(
            prompt=prompt,
            edition=edition,
        )


        generate_request.additional_properties = d
        return generate_request

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
