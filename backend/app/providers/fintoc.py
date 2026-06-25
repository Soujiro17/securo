import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import httpx

from app.core.config import get_settings
from app.providers.base import (
    AccountData,
    BankProvider,
    ConnectionData,
    ConnectTokenData,
    InstitutionData,
    InstitutionListData,
    ProviderRateLimited,
    RefreshOutcome,
    SessionExpiredError,
    TransactionData,
)

logger = logging.getLogger(__name__)

FINTOC_API_BASE = "https://api.fintoc.com/v1"

# Fintoc movements only contain settled (posted) entries — no pending state.
_DEFAULT_SYNC_DAYS = 90


def _map_account_type(fintoc_type: str) -> str:
    """Map Fintoc account type string to Securo account type.

    vista_account / sight_account (Cuenta Vista / Cuenta RUT) is Chile's most common
    demand-deposit account — structurally equivalent to a checking account.
    """
    mapping = {
        "checking_account": "checking",
        "savings_account": "savings",
        "vista_account": "checking",
        "sight_account": "checking",
    }
    return mapping.get(fintoc_type, "checking")


def _build_account_data(acc: dict) -> AccountData:
    """Map a Fintoc account payload to AccountData."""
    balance_obj = acc.get("balance") or {}
    balance = Decimal(str(balance_obj.get("available") or balance_obj.get("current") or 0))
    return AccountData(
        external_id=acc["id"],
        name=acc.get("official_name") or acc.get("name") or acc["id"],
        type=_map_account_type(acc.get("type", "")),
        balance=balance,
        currency=(acc.get("currency") or "CLP").upper(),
    )


def _build_transaction_data(mov: dict) -> TransactionData:
    """Map a Fintoc movement payload to TransactionData.

    CLP amounts from Fintoc are whole integer pesos — no scaling needed.
    Charge = money leaving the account (debit); deposit = money entering (credit).
    """
    tx_type = "debit" if mov.get("type") == "charge" else "credit"
    # post_date is the settlement date; fall back to transaction_date if absent.
    tx_date_str = mov.get("post_date") or mov.get("transaction_date")
    try:
        tx_date = date.fromisoformat(str(tx_date_str)[:10])
    except (TypeError, ValueError):
        tx_date = date.today()

    return TransactionData(
        external_id=str(mov["id"]),
        description=mov.get("description") or "",
        amount=Decimal(str(mov.get("amount", 0))),
        date=tx_date,
        type=tx_type,
        currency=(mov.get("currency") or "CLP").upper(),
        status="posted",
        raw_data=mov,
    )


class FintocProvider(BankProvider):
    """Bank account linking provider for Chilean banks via Fintoc (https://fintoc.com).

    Uses a widget-based connection flow (FintocLink) identical in structure to Pluggy.
    All API calls are made with httpx.AsyncClient — the synchronous fintoc pip package
    is intentionally not used to maintain async consistency with other providers.
    """

    @property
    def name(self) -> str:
        return "fintoc"

    @property
    def flow_type(self) -> str:
        return "widget"

    def _get_headers(self) -> dict:
        return {"Authorization": get_settings().fintoc_secret_key}

    def _raise_for_fintoc(self, response: httpx.Response) -> None:
        """Translate Fintoc HTTP error codes into provider exceptions."""
        if response.status_code == 401:
            raise SessionExpiredError("Fintoc link token is invalid or has been revoked")
        if response.status_code == 429:
            raise ProviderRateLimited("Fintoc rate limit exceeded")
        response.raise_for_status()

    async def get_oauth_url(
        self,
        redirect_uri: str,
        state: str,
        flow_params: Optional[dict] = None,
    ) -> str:
        raise NotImplementedError("Fintoc uses widget flow, not OAuth redirect")

    async def create_connect_token(
        self,
        client_user_id: str,
        item_id: str | None = None,
    ) -> ConnectTokenData:
        """Create a FintocLink widget token via POST /link_intents.

        item_id is unused for now — Fintoc's link_intents API does not support a
        direct refresh mode; re-authentication happens by creating a fresh intent.
        """
        payload = {
            "product": "movements",
            "country": "cl",
            "holder_type": "individual",
        }
        async with httpx.AsyncClient(headers=self._get_headers(), timeout=30) as client:
            response = await client.post(f"{FINTOC_API_BASE}/link_intents", json=payload)
            self._raise_for_fintoc(response)
            data = response.json()
        return ConnectTokenData(access_token=data["widget_token"])

    async def handle_oauth_callback(self, code: str) -> ConnectionData:
        """Exchange a FintocLink exchange_token for a ConnectionData.

        `code` is the exchange_token returned by the FintocLink widget onSuccess
        callback. POST /links exchanges it for the long-lived link_token and returns
        the full Link object (including accounts and institution) in one call.
        """
        async with httpx.AsyncClient(headers=self._get_headers(), timeout=30) as client:
            response = await client.post(
                f"{FINTOC_API_BASE}/links",
                json={"exchange_token": code},
            )
            self._raise_for_fintoc(response)
            link = response.json()

        link_token: str = link["link_token"]
        institution_name: str = (link.get("institution") or {}).get("name") or "Chilean Bank"
        accounts = [_build_account_data(acc) for acc in link.get("accounts") or []]

        return ConnectionData(
            external_id=link["id"],
            institution_name=institution_name,
            credentials={"link_token": link_token},
            accounts=accounts,
        )

    async def get_accounts(self, credentials: dict) -> list[AccountData]:
        link_token = credentials.get("link_token") or credentials.get("link_token_enc", "")
        async with httpx.AsyncClient(headers=self._get_headers(), timeout=30) as client:
            response = await client.get(
                f"{FINTOC_API_BASE}/accounts",
                params={"link_token": link_token},
            )
            self._raise_for_fintoc(response)
            return [_build_account_data(acc) for acc in response.json()]

    async def get_transactions(
        self,
        credentials: dict,
        account_external_id: str,
        since: Optional[date] = None,
        payee_source: str = "auto",
    ) -> list[TransactionData]:
        """Fetch movements for one account, handling cursor-based pagination."""
        link_token = credentials.get("link_token") or credentials.get("link_token_enc", "")
        since_date = since or (date.today() - timedelta(days=_DEFAULT_SYNC_DAYS))

        params: dict = {
            "link_token": link_token,
            "since": since_date.isoformat(),
        }

        results: list[TransactionData] = []
        async with httpx.AsyncClient(headers=self._get_headers(), timeout=60) as client:
            while True:
                response = await client.get(
                    f"{FINTOC_API_BASE}/accounts/{account_external_id}/movements",
                    params=params,
                )
                self._raise_for_fintoc(response)
                body = response.json()

                movements = body if isinstance(body, list) else body.get("data", [])
                results.extend(_build_transaction_data(mov) for mov in movements)

                # Fintoc paginates via next_cursor in the response envelope.
                next_cursor = None if isinstance(body, list) else body.get("next_cursor")
                if not next_cursor:
                    break
                params = {"link_token": link_token, "cursor": next_cursor}

        return results

    async def refresh_credentials(self, credentials: dict) -> dict:
        """No-op: Fintoc link tokens do not expire on a timer.

        Token invalidity surfaces as SessionExpiredError via _raise_for_fintoc()
        on the next API call (401 response).
        """
        return credentials

    async def trigger_refresh(self, credentials: dict) -> RefreshOutcome:
        """Fintoc returns live bank data on each API call — no explicit refresh needed."""
        return "skipped"

    async def list_institutions(self, country: Optional[str] = None) -> InstitutionListData:
        """Return Fintoc-supported institutions for Chile (or the specified country)."""
        target_country = country or "cl"
        async with httpx.AsyncClient(headers=self._get_headers(), timeout=30) as client:
            response = await client.get(
                f"{FINTOC_API_BASE}/institutions",
                params={"country": target_country},
            )
            self._raise_for_fintoc(response)
            raw = response.json()

        institutions = [
            InstitutionData(
                name=inst.get("id") or inst.get("name", ""),
                display_name=inst.get("name", ""),
                country=inst.get("country", target_country),
                logo=inst.get("logo_url") or inst.get("logo"),
            )
            for inst in (raw if isinstance(raw, list) else raw.get("data", []))
        ]
        return InstitutionListData(countries=[target_country], institutions=institutions)
