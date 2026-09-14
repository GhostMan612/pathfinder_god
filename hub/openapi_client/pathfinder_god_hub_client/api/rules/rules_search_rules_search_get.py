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

from ...models.http_validation_error import HTTPValidationError
from ...models.rules_search_response import RulesSearchResponse
from ...types import UNSET, Unset
from typing import cast



def _get_kwargs(
    *,
    q: str,
    edition: str | Unset = 'both',
    limit: int | Unset = 5,

) -> dict[str, Any]:
    

    

    params: dict[str, Any] = {}

    params["q"] = q

    params["edition"] = edition

    params["limit"] = limit


    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}


    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/rules/search",
        "params": params,
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | RulesSearchResponse | None:
    if response.status_code == 200:
        response_200 = RulesSearchResponse.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | RulesSearchResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str,
    edition: str | Unset = 'both',
    limit: int | Unset = 5,

) -> Response[HTTPValidationError | RulesSearchResponse]:
    """ Rules Search

     Raw rule/bestiary lookup (no LLM) — powers the app's rules browser.

    Args:
        q (str):
        edition (str | Unset):  Default: 'both'.
        limit (int | Unset):  Default: 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RulesSearchResponse]
     """


    kwargs = _get_kwargs(
        q=q,
edition=edition,
limit=limit,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    *,
    client: AuthenticatedClient | Client,
    q: str,
    edition: str | Unset = 'both',
    limit: int | Unset = 5,

) -> HTTPValidationError | RulesSearchResponse | None:
    """ Rules Search

     Raw rule/bestiary lookup (no LLM) — powers the app's rules browser.

    Args:
        q (str):
        edition (str | Unset):  Default: 'both'.
        limit (int | Unset):  Default: 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RulesSearchResponse
     """


    return sync_detailed(
        client=client,
q=q,
edition=edition,
limit=limit,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str,
    edition: str | Unset = 'both',
    limit: int | Unset = 5,

) -> Response[HTTPValidationError | RulesSearchResponse]:
    """ Rules Search

     Raw rule/bestiary lookup (no LLM) — powers the app's rules browser.

    Args:
        q (str):
        edition (str | Unset):  Default: 'both'.
        limit (int | Unset):  Default: 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RulesSearchResponse]
     """


    kwargs = _get_kwargs(
        q=q,
edition=edition,
limit=limit,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str,
    edition: str | Unset = 'both',
    limit: int | Unset = 5,

) -> HTTPValidationError | RulesSearchResponse | None:
    """ Rules Search

     Raw rule/bestiary lookup (no LLM) — powers the app's rules browser.

    Args:
        q (str):
        edition (str | Unset):  Default: 'both'.
        limit (int | Unset):  Default: 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RulesSearchResponse
     """


    return (await asyncio_detailed(
        client=client,
q=q,
edition=edition,
limit=limit,

    )).parsed
