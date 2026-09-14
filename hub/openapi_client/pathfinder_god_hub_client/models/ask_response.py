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

from ..models.ask_response_backend import AskResponseBackend
from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
  from ..models.rule_hit_model import RuleHitModel





T = TypeVar("T", bound="AskResponse")



@_attrs_define
class AskResponse:
    """ 
        Attributes:
            answer (str):
            backend (AskResponseBackend):
            mode (str):
            edition (str):
            sources (list[RuleHitModel] | Unset):
     """

    answer: str
    backend: AskResponseBackend
    mode: str
    edition: str
    sources: list[RuleHitModel] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        from ..models.rule_hit_model import RuleHitModel
        answer = self.answer

        backend = self.backend.value

        mode = self.mode

        edition = self.edition

        sources: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.sources, Unset):
            sources = []
            for sources_item_data in self.sources:
                sources_item = sources_item_data.to_dict()
                sources.append(sources_item)




        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "answer": answer,
            "backend": backend,
            "mode": mode,
            "edition": edition,
        })
        if sources is not UNSET:
            field_dict["sources"] = sources

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.rule_hit_model import RuleHitModel
        d = dict(src_dict)
        answer = d.pop("answer")

        backend = AskResponseBackend(d.pop("backend"))




        mode = d.pop("mode")

        edition = d.pop("edition")

        _sources = d.pop("sources", UNSET)
        sources: list[RuleHitModel] | Unset = UNSET
        if _sources is not UNSET:
            sources = []
            for sources_item_data in _sources:
                sources_item = RuleHitModel.from_dict(sources_item_data)



                sources.append(sources_item)


        ask_response = cls(
            answer=answer,
            backend=backend,
            mode=mode,
            edition=edition,
            sources=sources,
        )


        ask_response.additional_properties = d
        return ask_response

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
