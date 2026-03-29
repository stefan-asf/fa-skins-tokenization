// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./SkinToken.sol";

/// @title SkinVault
/// @notice Реестр: skinId (market_hash_name) → адрес SkinToken контракта.
///         Владелец (деплойер) может добавлять новые скины и управлять операторами.
contract SkinVault is Ownable {
    /// @notice Маппинг: keccak256(market_hash_name) → адрес SkinToken
    mapping(bytes32 => address) public skinTokens;

    /// @notice Адрес оператора (бэкенд), которому выдаётся OPERATOR_ROLE при создании токена
    address public operator;

    event SkinRegistered(string indexed skinId, address tokenAddress);
    event TokensMinted(address indexed to, string skinId, uint256 amount);
    event TokensBurned(address indexed from, string skinId, uint256 amount);

    constructor(address _operator) Ownable(msg.sender) {
        operator = _operator;
    }

    /// @notice Зарегистрировать новый скин и задеплоить для него SkinToken
    /// @param skinId  market_hash_name скина, напр. "AK-47 | Redline (Field-Tested)"
    /// @param name    Полное название токена
    /// @param symbol  Короткий символ токена
    function registerSkin(
        string calldata skinId,
        string calldata name,
        string calldata symbol
    ) external onlyOwner returns (address) {
        bytes32 key = keccak256(bytes(skinId));
        require(skinTokens[key] == address(0), "Skin already registered");

        SkinToken token = new SkinToken(name, symbol, operator);
        // Даём самому vault'у OPERATOR_ROLE, чтобы он мог вызывать mint/burn
        token.grantRole(token.OPERATOR_ROLE(), address(this));
        skinTokens[key] = address(token);

        emit SkinRegistered(skinId, address(token));
        return address(token);
    }

    /// @notice Получить адрес токена по skinId
    function getTokenAddress(string calldata skinId) external view returns (address) {
        return skinTokens[keccak256(bytes(skinId))];
    }

    /// @notice Выпустить токены (вызывается бэкендом напрямую через SkinToken)
    ///         Эта функция — удобная обёртка с эмитом события для event listener
    function mint(address to, string calldata skinId, uint256 amount) external {
        address tokenAddr = skinTokens[keccak256(bytes(skinId))];
        require(tokenAddr != address(0), "Skin not registered");

        SkinToken(tokenAddr).mint(to, amount);
        emit TokensMinted(to, skinId, amount);
    }

    /// @notice Сжечь токены (вызывается пользователем через approve, затем бэкендом)
    function burn(address from, string calldata skinId, uint256 amount) external {
        address tokenAddr = skinTokens[keccak256(bytes(skinId))];
        require(tokenAddr != address(0), "Skin not registered");

        SkinToken(tokenAddr).burn(from, amount);
        emit TokensBurned(from, skinId, amount);
    }

    /// @notice Обновить адрес оператора
    function setOperator(address _operator) external onlyOwner {
        operator = _operator;
    }
}
