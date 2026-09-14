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






T = TypeVar("T", bound="RuleHitModel")



@_attrs_define
class RuleHitModel:
    """ 
        Attributes:
            name (str):
            content (str):
            system (str | Unset):  Default: ''.
            category (str | Unset):  Default: ''.
            source_book (str | Unset):  Default: ''.
     """

    name: str
    content: str
    system: str | Unset = ''
    category: str | Unset = ''
    source_book: str | Unset = ''
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        name = self.name

        content = self.content

        system = self.system

        category = self.category

        source_book = self.source_book


        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "name": name,
            "content": content,
        })
        if system is not UNSET:
            field_dict["system"] = system
        if category is not UNSET:
            field_dict["category"] = category
        if source_book is not UNSET:
            field_dict["source_book"] = source_book

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        content = d.pop("content")

        system = d.pop("system", UNSET)

        category = d.pop("category", UNSET)

        source_book = d.pop("source_book", UNSET)

        rule_hit_model = cls(
            name=name,
            content=content,
            system=system,
            category=category,
            source_book=source_book,
        )


        rule_hit_model.additional_properties = d
        return rule_hit_model

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
