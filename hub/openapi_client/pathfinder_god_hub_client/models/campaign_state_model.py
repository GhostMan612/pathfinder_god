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

if TYPE_CHECKING:
  from ..models.campaign_note import CampaignNote
  from ..models.campaign_state_model_party_item import CampaignStateModelPartyItem





T = TypeVar("T", bound="CampaignStateModel")



@_attrs_define
class CampaignStateModel:
    """ 
        Attributes:
            party (list[CampaignStateModelPartyItem] | Unset):
            notes (list[CampaignNote] | Unset):
     """

    party: list[CampaignStateModelPartyItem] | Unset = UNSET
    notes: list[CampaignNote] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        from ..models.campaign_note import CampaignNote
        from ..models.campaign_state_model_party_item import CampaignStateModelPartyItem
        party: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.party, Unset):
            party = []
            for party_item_data in self.party:
                party_item = party_item_data.to_dict()
                party.append(party_item)



        notes: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.notes, Unset):
            notes = []
            for notes_item_data in self.notes:
                notes_item = notes_item_data.to_dict()
                notes.append(notes_item)




        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
        })
        if party is not UNSET:
            field_dict["party"] = party
        if notes is not UNSET:
            field_dict["notes"] = notes

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.campaign_note import CampaignNote
        from ..models.campaign_state_model_party_item import CampaignStateModelPartyItem
        d = dict(src_dict)
        _party = d.pop("party", UNSET)
        party: list[CampaignStateModelPartyItem] | Unset = UNSET
        if _party is not UNSET:
            party = []
            for party_item_data in _party:
                party_item = CampaignStateModelPartyItem.from_dict(party_item_data)



                party.append(party_item)


        _notes = d.pop("notes", UNSET)
        notes: list[CampaignNote] | Unset = UNSET
        if _notes is not UNSET:
            notes = []
            for notes_item_data in _notes:
                notes_item = CampaignNote.from_dict(notes_item_data)



                notes.append(notes_item)


        campaign_state_model = cls(
            party=party,
            notes=notes,
        )


        campaign_state_model.additional_properties = d
        return campaign_state_model

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
