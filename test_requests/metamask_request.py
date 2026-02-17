from web3 import Web3

# Подключение к Base Mainnet
w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))

# Адрес твоего кошелька
wallet = w3.to_checksum_address("0x2bE1876Fa7359eAd48ef69d4Ad813B4349923a77")

# aBasWETH (Aave v3 WETH на Base)
ABASWETH_ADDRESS = w3.to_checksum_address("0xD4a0e0b9149BCee3C920d2E00b5dE09138fd8bb7")

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]

contract = w3.eth.contract(address=ABASWETH_ADDRESS, abi=ERC20_ABI)

decimals = contract.functions.decimals().call()
raw_balance = contract.functions.balanceOf(wallet).call()

balance = raw_balance / 10**decimals

print(f"{balance}")

