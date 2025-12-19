"""
Helper utilities for Alpaca API interactions.
"""

import logging
from typing import Optional, Tuple

from alpaca.broker.client import BrokerClient

logger = logging.getLogger(__name__)


def get_alpaca_account_id(api_key: str, secret_key: str, sandbox: bool = True) -> Optional[str]:
    """
    Fetch Alpaca account ID via API.

    Args:
        api_key: Alpaca API key
        secret_key: Alpaca secret key
        sandbox: Whether to use sandbox/paper trading

    Returns:
        Account ID (UUID) or None if failed
    """
    try:
        client = BrokerClient(api_key=api_key, secret_key=secret_key, sandbox=sandbox)

        # List accounts and get the first one
        accounts = client.list_accounts()
        if not accounts:
            logger.error("No Alpaca accounts found")
            return None

        account_id = accounts[0].id
        logger.info(f"Fetched Alpaca account ID: {account_id}")
        return account_id

    except Exception as e:
        logger.error(f"Failed to fetch Alpaca account ID: {e}")
        return None


def get_alpaca_bank_id(
    api_key: str, secret_key: str, sandbox: bool = True, bank_index: int = 0
) -> Optional[str]:
    """
    Fetch Alpaca bank account ID via API.

    Args:
        api_key: Alpaca API key
        secret_key: Alpaca secret key
        sandbox: Whether to use sandbox/paper trading
        bank_index: Index of bank account to use (default: 0 for first)

    Returns:
        Bank ID (UUID) or None if failed
    """
    try:
        client = BrokerClient(api_key=api_key, secret_key=secret_key, sandbox=sandbox)

        # First get the account ID
        accounts = client.list_accounts()
        if not accounts:
            logger.error("No Alpaca accounts found")
            return None

        account_id = accounts[0].id

        # Get banks for this account
        banks = client.get_banks_for_account(account_id)

        if not banks:
            logger.warning("No bank accounts linked to Alpaca account")
            return None

        if bank_index >= len(banks):
            logger.warning(f"Bank index {bank_index} out of range. Using first bank.")
            bank_index = 0

        bank_id = banks[bank_index].id
        bank_name = banks[bank_index].bank_name
        logger.info(f"Fetched Alpaca bank ID: {bank_id} ({bank_name})")

        return bank_id

    except Exception as e:
        logger.error(f"Failed to fetch Alpaca bank ID: {e}")
        return None


def get_alpaca_ids(
    api_key: str, secret_key: str, sandbox: bool = True
) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch both Alpaca account ID and bank ID via API.

    Args:
        api_key: Alpaca API key
        secret_key: Alpaca secret key
        sandbox: Whether to use sandbox/paper trading

    Returns:
        Tuple of (account_id, bank_id) or (None, None) if failed
    """
    account_id = get_alpaca_account_id(api_key, secret_key, sandbox)
    bank_id = get_alpaca_bank_id(api_key, secret_key, sandbox)

    return account_id, bank_id
