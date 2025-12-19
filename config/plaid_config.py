"""Plaid API configuration."""

import os

from plaid import ApiClient, ApiException, Configuration
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.transactions_sync_request_options import TransactionsSyncRequestOptions


class PlaidConfig:
    def __init__(self):
        self.PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
        self.PLAID_SECRET = os.getenv("PLAID_SECRET")
        self.PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")
        self.PLAID_PRODUCTS = os.getenv("PLAID_PRODUCTS", "transactions").split(",")
        self.PLAID_COUNTRY_CODES = os.getenv("PLAID_COUNTRY_CODES", "US").split(",")
        self.PLAID_REDIRECT_URI = os.getenv("PLAID_REDIRECT_URI", "")

        if not self.PLAID_CLIENT_ID or not self.PLAID_SECRET:
            raise ValueError(
                "PLAID_CLIENT_ID and PLAID_SECRET must be set in environment variables"
            )

        # Configure Plaid client
        configuration = Configuration(
            host=self._get_plaid_host(),
            api_key={
                "clientId": self.PLAID_CLIENT_ID,
                "secret": self.PLAID_SECRET,
                "plaidVersion": "2020-09-14",
            },
        )

        api_client = ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)

    def _get_plaid_host(self):
        return {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }.get(self.PLAID_ENV, "https://sandbox.plaid.com")

    async def create_link_token(self, user_id: str):
        """Create a link token for the Plaid Link UI."""
        request = LinkTokenCreateRequest(
            products=[Products(prod) for prod in self.PLAID_PRODUCTS],
            client_name="InvestorMimic Bot",
            country_codes=[CountryCode(code) for code in self.PLAID_COUNTRY_CODES],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=user_id),
        )

        if self.PLAID_REDIRECT_URI:
            request["redirect_uri"] = self.PLAID_REDIRECT_URI

        response = await self.client.link_token_create(request)
        return response["link_token"]


# Create a singleton instance
plaid_config = PlaidConfig()
