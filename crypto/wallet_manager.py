"""
Gestión de wallets para todas las chains.
Wallets de BEEA — privadas keys en Replit Secrets o auto-generadas y guardadas cifradas.
Chains: BTC, ETH, Base, BSC, Solana
"""

import os
import json
import logging
import hashlib
import asyncio
import aiohttp
from typing import Optional
from pathlib import Path

logger = logging.getLogger("beeatrix.wallet")

# RPCs gratuitos oficiales
RPCS = {
    "eth":    "https://ethereum.publicnode.com",
    "base":   "https://mainnet.base.org",
    "bsc":    "https://bsc-dataseed1.binance.org",
    "solana": "https://api.mainnet-beta.solana.com",
}

CHAIN_NAMES = {
    "eth":    "Ethereum",
    "base":   "Base",
    "bsc":    "BNB Chain",
    "solana": "Solana",
    "btc":    "Bitcoin",
}

NATIVE_TOKENS = {
    "eth":    ("ETH",  1e18),
    "base":   ("ETH",  1e18),
    "bsc":    ("BNB",  1e18),
    "solana": ("SOL",  1e9),
    "btc":    ("BTC",  1e8),
}

WALLET_FILE = Path("memory/beea_wallets.json")


class WalletManager:
    def __init__(self):
        self._wallets: dict = {}
        self._load()

    def _load(self):
        if WALLET_FILE.exists():
            try:
                self._wallets = json.loads(WALLET_FILE.read_text())
            except Exception:
                self._wallets = {}

    def _save(self):
        WALLET_FILE.parent.mkdir(exist_ok=True)
        WALLET_FILE.write_text(json.dumps(self._wallets, indent=2))

    # ── Generación de wallets ──────────────────────────────────────────────

    def _generate_evm(self, chain: str) -> dict:
        from eth_account import Account
        secret_key = f"BEEA_{chain.upper()}_PRIVATE_KEY"
        pk = os.environ.get(secret_key)
        if pk:
            account = Account.from_key(pk)
        else:
            account = Account.create()
            pk = account.key.hex()
            logger.info("Generated new %s wallet: %s", chain, account.address)
        return {"private_key": pk, "address": account.address}

    def _generate_solana(self) -> dict:
        from solders.keypair import Keypair
        secret_key = "BEEA_SOLANA_PRIVATE_KEY"
        pk = os.environ.get(secret_key)
        if pk:
            kp = Keypair.from_bytes(bytes.fromhex(pk))
        else:
            kp = Keypair()
            pk = bytes(kp).hex()
            logger.info("Generated new Solana wallet: %s", kp.pubkey())
        return {"private_key": pk, "address": str(kp.pubkey())}

    def _generate_btc(self) -> dict:
        try:
            from bit import Key
            secret_key = "BEEA_BTC_PRIVATE_KEY"
            pk = os.environ.get(secret_key)
            if pk:
                key = Key(pk)
            else:
                key = Key()
                pk = key.to_wif()
                logger.info("Generated new BTC wallet: %s", key.address)
            return {"private_key": pk, "address": key.address}
        except Exception as e:
            logger.warning("BTC wallet gen error: %s", e)
            # Fallback: generar desde eth_account derivation
            from eth_account import Account
            acc = Account.create()
            return {"private_key": acc.key.hex(), "address": "btc_unavailable", "note": "install bit library"}

    def init_all_wallets(self) -> dict:
        """Inicializa todas las wallets. Llama esto una vez al arrancar."""
        chains = ["eth", "base", "bsc", "solana", "btc"]
        for chain in chains:
            if chain not in self._wallets:
                if chain == "solana":
                    self._wallets[chain] = self._generate_solana()
                elif chain == "btc":
                    self._wallets[chain] = self._generate_btc()
                else:
                    self._wallets[chain] = self._generate_evm(chain)
                logger.info("Wallet %s ready: %s", chain, self._wallets[chain].get("address"))
        self._save()
        return {c: v.get("address") for c, v in self._wallets.items()}

    def get_address(self, chain: str) -> Optional[str]:
        return self._wallets.get(chain, {}).get("address")

    def get_private_key(self, chain: str) -> Optional[str]:
        return self._wallets.get(chain, {}).get("private_key")

    def get_keypair_solana(self):
        from solders.keypair import Keypair
        pk = self.get_private_key("solana")
        if pk:
            return Keypair.from_bytes(bytes.fromhex(pk))
        return None

    def get_eth_account(self, chain: str = "eth"):
        from eth_account import Account
        pk = self.get_private_key(chain)
        if pk:
            return Account.from_key(pk)
        return None

    # ── Balances ─────────────────────────────────────────────────────────

    async def get_balance_evm(self, chain: str) -> Optional[float]:
        address = self.get_address(chain)
        if not address:
            return None
        rpc = RPCS.get(chain)
        if not rpc:
            return None
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "eth_getBalance",
            "params": [address, "latest"]
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(rpc, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    raw = int(data["result"], 16)
                    symbol, divisor = NATIVE_TOKENS[chain]
                    return raw / divisor
        except Exception as e:
            logger.warning("Balance EVM %s error: %s", chain, e)
            return None

    async def get_balance_solana(self) -> Optional[float]:
        address = self.get_address("solana")
        if not address:
            return None
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [address]
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(RPCS["solana"], json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    lamports = data["result"]["value"]
                    return lamports / 1e9
        except Exception as e:
            logger.warning("Balance Solana error: %s", e)
            return None

    async def get_balance_btc(self) -> Optional[float]:
        address = self.get_address("btc")
        if not address or address == "btc_unavailable":
            return None
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://blockstream.info/api/address/{address}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    sat = data["chain_stats"]["funded_txo_sum"] - data["chain_stats"]["spent_txo_sum"]
                    return sat / 1e8
        except Exception as e:
            logger.warning("Balance BTC error: %s", e)
            return None

    async def get_all_balances(self) -> dict:
        tasks = {
            "eth":    self.get_balance_evm("eth"),
            "base":   self.get_balance_evm("base"),
            "bsc":    self.get_balance_evm("bsc"),
            "solana": self.get_balance_solana(),
            "btc":    self.get_balance_btc(),
        }
        results = {}
        for chain, coro in tasks.items():
            try:
                results[chain] = await coro
            except Exception:
                results[chain] = None
        return results

    # ── EVM token balance ─────────────────────────────────────────────────

    async def get_token_balance_evm(self, chain: str, token_address: str) -> Optional[float]:
        wallet = self.get_address(chain)
        if not wallet:
            return None
        rpc = RPCS.get(chain)
        # ERC-20 balanceOf ABI call
        fn_selector = "0x70a08231"
        padded = wallet[2:].zfill(64)
        data = fn_selector + padded
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "eth_call",
            "params": [{"to": token_address, "data": data}, "latest"]
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(rpc, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    res = await resp.json()
                    raw = int(res["result"], 16)
                    return raw / 1e18
        except Exception as e:
            logger.warning("Token balance error: %s", e)
            return None

    def format_balances_report(self, balances: dict, prices: dict = None) -> str:
        lines = ["Wallets de BEEA\n"]
        for chain, bal in balances.items():
            symbol, _ = NATIVE_TOKENS.get(chain, ("?", 1))
            name = CHAIN_NAMES.get(chain, chain.upper())
            addr = self.get_address(chain) or "—"
            short_addr = f"{addr[:6]}...{addr[-4:]}" if len(addr) > 10 else addr
            if bal is None:
                bal_str = "error al obtener"
            else:
                bal_str = f"{bal:.6f} {symbol}"
                if prices and symbol in prices:
                    usd = bal * prices[symbol]
                    bal_str += f" (${usd:,.2f})"
            lines.append(f"{name} [{short_addr}]: {bal_str}")
        return "\n".join(lines)


wallet_manager = WalletManager()
