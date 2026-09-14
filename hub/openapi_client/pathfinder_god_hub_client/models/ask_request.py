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

from ..models.ask_request_edition import AskRequestEdition
from ..models.ask_request_mode_type_0 import AskRequestModeType0
from ..types import UNSET, Unset
from typing import cast






T = TypeVar("T", bound="AskRequest")



@_attrs_define
class AskRequest:
    """ 
        Attributes:
            query (str): The GM question or free-form request.
            edition (AskRequestEdition | Unset):  Default: AskRequestEdition.BOTH.
            mode (AskRequestModeType0 | None | Unset): Force a generation mode; omit to auto-detect.
            history (list[list[str]] | Unset): Recent (speaker, message) turns for continuity, e.g. ('user', '...').
     """

    query: str
    edition: AskRequestEdition | Unset = AskRequestEdition.BOTH
    mode: AskRequestModeType0 | None | Unset = UNSET
    history: list[list[str]] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        query = self.query

        edition: str | Unset = UNSET
        if not isinstance(self.edition, Unset):
            edition = self.edition.value


        mode: None | str | Unset
        if isinstance(self.mode, Unset):
            mode = UNSET
        elif isinstance(self.mode, AskRequestModeType0):
            mode = self.mode.value
        else:
            mode = self.mode

        history: list[list[str]] | Unset = UNSET
        if not isinstance(self.history, Unset):
            history = []
            for history_item_data in self.history:
                history_item = []
                for history_item_item_data in history_item_data:
                    history_item_item: str
                    history_item_item = history_item_item_data
                    history_item.append(history_item_item)


                history.append(history_item)




        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "query": query,
        })
        if edition is not UNSET:
            field_dict["edition"] = edition
        if mode is not UNSET:
            field_dict["mode"] = mode
        if history is not UNSET:
            field_dict["history"] = history

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        query = d.pop("query")

        _edition = d.pop("edition", UNSET)
        edition: AskRequestEdition | Unset
        if isinstance(_edition,  Unset):
            edition = UNSET
        else:
            edition = AskRequestEdition(_edition)




        def _parse_mode(data: object) -> AskRequestModeType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                mode_type_0 = AskRequestModeType0(data)



                return mode_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(AskRequestModeType0 | None | Unset, data)

        mode = _parse_mode(d.pop("mode", UNSET))


        _history = d.pop("history", UNSET)
        history: list[list[str]] | Unset = UNSET
        if _history is not UNSET:
            history = []
            for history_item_data in _history:
                history_item = []
                _history_item = history_item_data
                for history_item_item_data in (_history_item):
                    def _parse_history_item_item(data: object) -> str:
                        return cast(str, data)

                    history_item_item = _parse_history_item_item(history_item_item_data)

                    history_item.append(history_item_item)

                history.append(history_item)


        ask_request = cls(
            query=query,
            edition=edition,
            mode=mode,
            history=history,
        )


        ask_request.additional_properties = d
        return ask_request

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
