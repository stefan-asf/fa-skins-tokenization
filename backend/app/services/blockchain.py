from web3 import Web3

from app.config import settings

SKIN_TOKEN_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "mint",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "burn",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
]

TOKEN_AMOUNT = Web3.to_wei(1, "ether")  # 1 токен = 1 скин


def _get_w3() -> Web3:
    return Web3(Web3.HTTPProvider(settings.sepolia_rpc_url))


def _get_contract(w3: Web3):
    return w3.eth.contract(
        address=Web3.to_checksum_address(settings.skin_token_address),
        abi=SKIN_TOKEN_ABI,
    )


def mint_token(wallet_address: str) -> str:
    """Минтит 1 токен на кошелёк пользователя. Возвращает tx_hash."""
    w3 = _get_w3()
    contract = _get_contract(w3)
    account = w3.eth.account.from_key(settings.deployer_private_key)

    tx = contract.functions.mint(
        Web3.to_checksum_address(wallet_address),
        TOKEN_AMOUNT,
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 100_000,
        "gasPrice": w3.eth.gas_price,
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def burn_token(wallet_address: str) -> str:
    """Сжигает 1 токен с кошелька пользователя. Возвращает tx_hash."""
    w3 = _get_w3()
    contract = _get_contract(w3)
    account = w3.eth.account.from_key(settings.deployer_private_key)

    tx = contract.functions.burn(
        Web3.to_checksum_address(wallet_address),
        TOKEN_AMOUNT,
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 100_000,
        "gasPrice": w3.eth.gas_price,
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def get_balance(wallet_address: str) -> int:
    """Возвращает количество токенов на кошельке (в wei)."""
    w3 = _get_w3()
    contract = _get_contract(w3)
    return contract.functions.balanceOf(
        Web3.to_checksum_address(wallet_address)
    ).call()
