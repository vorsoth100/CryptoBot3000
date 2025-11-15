"""
Coinbase Advanced Trade API Client
Handles all interactions with Coinbase Advanced Trade API
"""

import os
import time
import hmac
import hashlib
import json
import requests
import logging
import jwt
from typing import Dict, List, Optional, Any
from datetime import datetime


class CoinbaseClient:
    """Client for Coinbase Advanced Trade API"""

    BASE_URL_LIVE = "https://api.coinbase.com"
    BASE_URL_SANDBOX = "https://api-public.sandbox.exchange.coinbase.com"

    def __init__(self, api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 sandbox: bool = False):
        """
        Initialize Coinbase client

        Args:
            api_key: Coinbase API key (or from env COINBASE_API_KEY)
                    - CDP keys: "organizations/{org_id}/apiKeys/{key_id}"
                    - Legacy keys: alphanumeric string
            api_secret: Coinbase API secret (or from env COINBASE_API_SECRET)
                       - CDP keys: PEM format EC private key
                       - Legacy keys: alphanumeric string
            sandbox: Use sandbox environment for testing
        """
        self.api_key = api_key or os.getenv("COINBASE_API_KEY")
        self.api_secret = api_secret or os.getenv("COINBASE_API_SECRET")
        self.base_url = self.BASE_URL_SANDBOX if sandbox else self.BASE_URL_LIVE
        self.logger = logging.getLogger("CryptoBot.Coinbase")

        # Detect authentication type
        self.is_cdp_key = self.api_key and self.api_key.startswith("organizations/")

        if not self.api_key or not self.api_secret:
            self.logger.warning("Coinbase API credentials not set")
        else:
            # Debug: Log credential info (without exposing secrets)
            auth_type = "CDP (Cloud)" if self.is_cdp_key else "Legacy"
            self.logger.info(f"Authentication type: {auth_type}")
            self.logger.info(f"API Key length: {len(self.api_key)}, Secret length: {len(self.api_secret)}")
            self.logger.info(f"API Key starts with: {self.api_key[:20]}...")
            self.logger.info(f"Using base URL: {self.base_url}")

    def _generate_jwt_token(self, uri: str) -> str:
        """
        Generate JWT token for CDP API authentication

        Args:
            uri: Request URI (e.g., GET api.coinbase.com/api/v3/brokerage/accounts)

        Returns:
            JWT token string
        """
        import secrets

        # Build JWT
        now = int(time.time())
        payload = {
            "sub": self.api_key,
            "iss": "coinbase-cloud",
            "nbf": now,
            "exp": now + 120,  # Token valid for 2 minutes
            "aud": ["cdp_service"],
            "uri": uri
        }

        # Generate nonce
        nonce = secrets.token_hex(16)
        payload["nonce"] = nonce

        # Sign with ES256 algorithm
        token = jwt.encode(
            payload,
            self.api_secret,
            algorithm="ES256",
            headers={"kid": self.api_key, "nonce": nonce}
        )

        return token

    def _generate_signature(self, timestamp: str, method: str,
                          path: str, body: str = "") -> str:
        """
        Generate request signature for Legacy Key authentication

        Args:
            timestamp: Unix timestamp
            method: HTTP method (GET, POST, DELETE)
            path: Request path
            body: Request body (if any)

        Returns:
            HMAC signature (hex encoded - lowercase)
        """
        message = timestamp + method + path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return signature.hex()

    def _make_request(self, method: str, endpoint: str,
                     params: Optional[Dict] = None,
                     data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make authenticated request to Coinbase API

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint (e.g., /api/v3/brokerage/accounts)
            params: Query parameters
            data: Request body data

        Returns:
            Response JSON or None on error
        """
        if not self.api_key or not self.api_secret:
            self.logger.error("API credentials not configured")
            return None

        url = self.base_url + endpoint

        # Build headers based on authentication type
        if self.is_cdp_key:
            # CDP API Key - Use JWT authentication
            uri = f"{method} {self.base_url.replace('https://', '')}{endpoint}"
            self.logger.debug(f"Generating JWT for URI: {uri}")

            try:
                token = self._generate_jwt_token(uri)
                self.logger.debug(f"JWT token generated (first 30 chars): {token[:30]}...")

                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            except Exception as e:
                self.logger.error(f"Failed to generate JWT token: {e}")
                return None
        else:
            # Legacy API Key - Use HMAC signature
            timestamp = str(int(time.time()))
            body = ""
            if data:
                body = json.dumps(data)

            self.logger.debug(f"Request: {method} {endpoint}")
            self.logger.debug(f"Timestamp: {timestamp}")
            self.logger.debug(f"Message to sign: {timestamp}{method}{endpoint}{body}")

            signature = self._generate_signature(timestamp, method, endpoint, body)
            self.logger.debug(f"Signature (first 20 chars): {signature[:20]}...")

            headers = {
                "CB-ACCESS-KEY": self.api_key,
                "CB-ACCESS-SIGN": signature,
                "CB-ACCESS-TIMESTAMP": timestamp,
                "Content-Type": "application/json"
            }

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                self.logger.error(f"Unsupported HTTP method: {method}")
                return None

            self.logger.debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response status: {e.response.status_code}")
                self.logger.error(f"Response headers: {dict(e.response.headers)}")
                self.logger.error(f"Response body: {e.response.text}")
            return None

    def get_accounts(self) -> Optional[List[Dict]]:
        """
        Get all account balances

        Returns:
            List of account dictionaries
        """
        response = self._make_request("GET", "/api/v3/brokerage/accounts")
        if response and "accounts" in response:
            return response["accounts"]
        return None

    def get_balance(self, currency: str = "USD") -> Optional[float]:
        """
        Get balance for specific currency

        Args:
            currency: Currency code (e.g., USD, BTC)

        Returns:
            Available balance
        """
        accounts = self.get_accounts()
        if not accounts:
            return None

        for account in accounts:
            if account.get("currency") == currency:
                return float(account.get("available_balance", {}).get("value", 0))

        return 0.0

    def get_products(self) -> Optional[List[Dict]]:
        """
        Get all available trading products

        Returns:
            List of product dictionaries
        """
        response = self._make_request("GET", "/api/v3/brokerage/products")
        if response and "products" in response:
            return response["products"]
        return None

    def get_product(self, product_id: str) -> Optional[Dict]:
        """
        Get details for a specific product

        Args:
            product_id: Product ID (e.g., BTC-USD)

        Returns:
            Product details
        """
        response = self._make_request("GET", f"/api/v3/brokerage/products/{product_id}")
        return response

    def get_ticker(self, product_id: str) -> Optional[Dict]:
        """
        Get current ticker/price for a product

        Args:
            product_id: Product ID (e.g., BTC-USD)

        Returns:
            Ticker data with price, volume, etc.
        """
        response = self._make_request(
            "GET",
            f"/api/v3/brokerage/products/{product_id}/ticker"
        )
        return response

    def get_current_price(self, product_id: str) -> Optional[float]:
        """
        Get current price for a product

        Args:
            product_id: Product ID (e.g., BTC-USD)

        Returns:
            Current price
        """
        ticker = self.get_ticker(product_id)
        if ticker and "price" in ticker:
            return float(ticker["price"])
        return None

    def get_candles(self, product_id: str, granularity: str = "ONE_HOUR",
                   start: Optional[str] = None, end: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Get historical candles for a product

        Args:
            product_id: Product ID (e.g., BTC-USD)
            granularity: Candle size (ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE,
                        ONE_HOUR, SIX_HOUR, ONE_DAY)
            start: Start time (ISO 8601)
            end: End time (ISO 8601)

        Returns:
            List of candle dictionaries
        """
        params = {"granularity": granularity}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        response = self._make_request(
            "GET",
            f"/api/v3/brokerage/products/{product_id}/candles",
            params=params
        )

        if response and "candles" in response:
            return response["candles"]
        return None

    def place_limit_order(self, product_id: str, side: str,
                         quantity: float, price: float,
                         post_only: bool = True) -> Optional[Dict]:
        """
        Place a limit order

        Args:
            product_id: Product ID (e.g., BTC-USD)
            side: BUY or SELL
            quantity: Order quantity
            price: Limit price
            post_only: True for maker-only (recommended to avoid taker fees)

        Returns:
            Order response
        """
        data = {
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": {
                "limit_limit_gtc": {
                    "base_size": str(quantity),
                    "limit_price": str(price),
                    "post_only": post_only
                }
            }
        }

        response = self._make_request("POST", "/api/v3/brokerage/orders", data=data)

        if response:
            self.logger.info(
                f"[ORDER] Placed {side} limit order: {quantity} {product_id} @ ${price}"
            )

        return response

    def place_market_order(self, product_id: str, side: str,
                          amount_usd: Optional[float] = None,
                          quantity: Optional[float] = None) -> Optional[Dict]:
        """
        Place a market order (higher fees - use sparingly)

        Args:
            product_id: Product ID (e.g., BTC-USD)
            side: BUY or SELL
            amount_usd: Amount in USD (for buys)
            quantity: Quantity to sell (for sells)

        Returns:
            Order response
        """
        if side.upper() == "BUY":
            if not amount_usd:
                self.logger.error("amount_usd required for market buy")
                return None

            data = {
                "product_id": product_id,
                "side": "BUY",
                "order_configuration": {
                    "market_market_ioc": {
                        "quote_size": str(amount_usd)
                    }
                }
            }
        else:  # SELL
            if not quantity:
                self.logger.error("quantity required for market sell")
                return None

            data = {
                "product_id": product_id,
                "side": "SELL",
                "order_configuration": {
                    "market_market_ioc": {
                        "base_size": str(quantity)
                    }
                }
            }

        response = self._make_request("POST", "/api/v3/brokerage/orders", data=data)

        if response:
            self.logger.warning(
                f"[ORDER] Placed {side} MARKET order (HIGH FEES): {product_id}"
            )

        return response

    def cancel_order(self, order_id: str) -> Optional[Dict]:
        """
        Cancel an order

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        response = self._make_request(
            "DELETE",
            f"/api/v3/brokerage/orders/{order_id}"
        )

        if response:
            self.logger.info(f"[ORDER] Cancelled order {order_id}")

        return response

    def get_order(self, order_id: str) -> Optional[Dict]:
        """
        Get order details

        Args:
            order_id: Order ID

        Returns:
            Order details
        """
        response = self._make_request(
            "GET",
            f"/api/v3/brokerage/orders/historical/{order_id}"
        )
        return response

    def get_orders(self, product_id: Optional[str] = None,
                  limit: int = 100) -> Optional[List[Dict]]:
        """
        Get list of orders

        Args:
            product_id: Filter by product (optional)
            limit: Maximum number of orders to return

        Returns:
            List of orders
        """
        params = {"limit": limit}
        if product_id:
            params["product_id"] = product_id

        response = self._make_request(
            "GET",
            "/api/v3/brokerage/orders/historical/batch",
            params=params
        )

        if response and "orders" in response:
            return response["orders"]
        return None

    def test_connection(self) -> bool:
        """
        Test API connection and credentials

        Returns:
            True if connection successful
        """
        try:
            accounts = self.get_accounts()
            if accounts is not None:
                self.logger.info("✓ Coinbase API connection successful")
                return True
            else:
                self.logger.error("✗ Coinbase API connection failed")
                return False
        except Exception as e:
            self.logger.error(f"✗ Coinbase API test failed: {e}")
            return False

    def get_position(self, currency: str) -> Optional[Dict]:
        """
        Get current position/holdings for a currency

        Args:
            currency: Currency code (e.g., BTC, ETH)

        Returns:
            Position details with balance and value
        """
        accounts = self.get_accounts()
        if not accounts:
            return None

        for account in accounts:
            if account.get("currency") == currency:
                balance = float(account.get("available_balance", {}).get("value", 0))
                hold = float(account.get("hold", {}).get("value", 0))

                return {
                    "currency": currency,
                    "balance": balance,
                    "hold": hold,
                    "total": balance + hold,
                    "account_id": account.get("uuid")
                }

        return None
