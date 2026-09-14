# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.ask_response import AskResponse
from ...models.generate_request import GenerateRequest
from ...models.http_validation_error import HTTPValidationError
from typing import cast



def _get_kwargs(
    kind: str,
    *,
    body: GenerateRequest,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/generate/{kind}".format(kind=quote(str(kind), safe=""),),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> AskResponse | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = AskResponse.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[AskResponse | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    kind: str,
    *,
    client: AuthenticatedClient | Client,
    body: GenerateRequest,

) -> Response[AskResponse | HTTPValidationError]:
    """ Generate

     Typed generators — the God's core creative powers.

    ``kind`` is one of: character, npc, monster, boss, map, campaign, encounter.
    Each forces the matching mode so you always get full bios/backstories.
    Unknown kinds fall back to auto-detection from the raw prompt.

    Args:
        kind (str):
        body (GenerateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AskResponse | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        kind=kind,
body=body,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    kind: str,
    *,
    client: AuthenticatedClient | Client,
    body: GenerateRequest,

) -> AskResponse | HTTPValidationError | None:
    """ Generate

     Typed generators — the God's core creative powers.

    ``kind`` is one of: character, npc, monster, boss, map, campaign, encounter.
    Each forces the matching mode so you always get full bios/backstories.
    Unknown kinds fall back to auto-detection from the raw prompt.

    Args:
        kind (str):
        body (GenerateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AskResponse | HTTPValidationError
     """


    return sync_detailed(
        kind=kind,
client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    kind: str,
    *,
    client: AuthenticatedClient | Client,
    body: GenerateRequest,

) -> Response[AskResponse | HTTPValidationError]:
    """ Generate

     Typed generators — the God's core creative powers.

    ``kind`` is one of: character, npc, monster, boss, map, campaign, encounter.
    Each forces the matching mode so you always get full bios/backstories.
    Unknown kinds fall back to auto-detection from the raw prompt.

    Args:
        kind (str):
        body (GenerateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AskResponse | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        kind=kind,
body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    kind: str,
    *,
    client: AuthenticatedClient | Client,
    body: GenerateRequest,

) -> AskResponse | HTTPValidationError | None:
    """ Generate

     Typed generators — the God's core creative powers.

    ``kind`` is one of: character, npc, monster, boss, map, campaign, encounter.
    Each forces the matching mode so you always get full bios/backstories.
    Unknown kinds fall back to auto-detection from the raw prompt.

    Args:
        kind (str):
        body (GenerateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AskResponse | HTTPValidationError
     """


    return (await asyncio_detailed(
        kind=kind,
client=client,
body=body,

    )).parsed
