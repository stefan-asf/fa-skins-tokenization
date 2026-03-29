// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

/// @title SkinToken
/// @notice ERC-20 токен для одного типа скина CS2.
///         mint() и burn() доступны только оператору (бэкенду).
contract SkinToken is ERC20, AccessControl {
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    /// @param name    Название скина, напр. "AK-47 | Redline"
    /// @param symbol  Краткий символ, напр. "AK47RL"
    /// @param operator Адрес бэкенда, который будет вызывать mint/burn
    constructor(
        string memory name,
        string memory symbol,
        address operator
    ) ERC20(name, symbol) {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(OPERATOR_ROLE, operator);
    }

    /// @notice Выпустить токены пользователю после получения скина ботом
    /// @param to     Кошелёк пользователя
    /// @param amount Количество токенов (с учётом decimals = 18)
    function mint(address to, uint256 amount) external onlyRole(OPERATOR_ROLE) {
        _mint(to, amount);
    }

    /// @notice Сжечь токены пользователя при выводе скина
    /// @param from   Кошелёк пользователя
    /// @param amount Количество токенов
    function burn(address from, uint256 amount) external onlyRole(OPERATOR_ROLE) {
        _burn(from, amount);
    }

    /// @notice Добавить нового оператора (например второй бэкенд)
    function addOperator(address operator) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _grantRole(OPERATOR_ROLE, operator);
    }

    /// @notice Убрать оператора
    function removeOperator(address operator) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _revokeRole(OPERATOR_ROLE, operator);
    }
}
