const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SkinToken", function () {
  let skinToken, owner, operator, user, other;

  beforeEach(async function () {
    [owner, operator, user, other] = await ethers.getSigners();
    const SkinToken = await ethers.getContractFactory("SkinToken");
    skinToken = await SkinToken.deploy("AK-47 | Redline", "AK47RL", operator.address);
  });

  it("устанавливает правильное название и символ", async function () {
    expect(await skinToken.name()).to.equal("AK-47 | Redline");
    expect(await skinToken.symbol()).to.equal("AK47RL");
  });

  it("оператор может сделать mint", async function () {
    await skinToken.connect(operator).mint(user.address, ethers.parseEther("1"));
    expect(await skinToken.balanceOf(user.address)).to.equal(ethers.parseEther("1"));
  });

  it("не-оператор не может сделать mint", async function () {
    await expect(
      skinToken.connect(other).mint(user.address, ethers.parseEther("1"))
    ).to.be.reverted;
  });

  it("оператор может сделать burn", async function () {
    await skinToken.connect(operator).mint(user.address, ethers.parseEther("1"));
    await skinToken.connect(operator).burn(user.address, ethers.parseEther("1"));
    expect(await skinToken.balanceOf(user.address)).to.equal(0);
  });

  it("нельзя сжечь больше баланса", async function () {
    await skinToken.connect(operator).mint(user.address, ethers.parseEther("1"));
    await expect(
      skinToken.connect(operator).burn(user.address, ethers.parseEther("2"))
    ).to.be.reverted;
  });

  it("владелец может добавить и убрать оператора", async function () {
    const OPERATOR_ROLE = await skinToken.OPERATOR_ROLE();
    await skinToken.connect(owner).addOperator(other.address);
    expect(await skinToken.hasRole(OPERATOR_ROLE, other.address)).to.be.true;

    await skinToken.connect(owner).removeOperator(other.address);
    expect(await skinToken.hasRole(OPERATOR_ROLE, other.address)).to.be.false;
  });
});
