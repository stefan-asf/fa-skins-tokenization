const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SkinVault", function () {
  let skinVault, owner, operator, user;
  const SKIN_ID = "AK-47 | Redline (Field-Tested)";

  beforeEach(async function () {
    [owner, operator, user] = await ethers.getSigners();
    const SkinVault = await ethers.getContractFactory("SkinVault");
    skinVault = await SkinVault.deploy(operator.address);
  });

  it("регистрирует новый скин и создаёт SkinToken", async function () {
    await skinVault.connect(owner).registerSkin(SKIN_ID, "AK-47 Redline", "AK47RL");
    const tokenAddr = await skinVault.getTokenAddress(SKIN_ID);
    expect(tokenAddr).to.not.equal(ethers.ZeroAddress);
  });

  it("нельзя зарегистрировать один скин дважды", async function () {
    await skinVault.connect(owner).registerSkin(SKIN_ID, "AK-47 Redline", "AK47RL");
    await expect(
      skinVault.connect(owner).registerSkin(SKIN_ID, "AK-47 Redline", "AK47RL")
    ).to.be.revertedWith("Skin already registered");
  });

  it("оператор может mint через vault", async function () {
    await skinVault.connect(owner).registerSkin(SKIN_ID, "AK-47 Redline", "AK47RL");
    const tokenAddr = await skinVault.getTokenAddress(SKIN_ID);
    const SkinToken = await ethers.getContractFactory("SkinToken");
    const token = SkinToken.attach(tokenAddr);

    await skinVault.connect(operator).mint(user.address, SKIN_ID, ethers.parseEther("1"));
    expect(await token.balanceOf(user.address)).to.equal(ethers.parseEther("1"));
  });

  it("эмитит событие TokensMinted", async function () {
    await skinVault.connect(owner).registerSkin(SKIN_ID, "AK-47 Redline", "AK47RL");
    await expect(
      skinVault.connect(operator).mint(user.address, SKIN_ID, ethers.parseEther("1"))
    ).to.emit(skinVault, "TokensMinted").withArgs(user.address, SKIN_ID, ethers.parseEther("1"));
  });

  it("оператор может burn через vault и эмитит TokensBurned", async function () {
    await skinVault.connect(owner).registerSkin(SKIN_ID, "AK-47 Redline", "AK47RL");
    await skinVault.connect(operator).mint(user.address, SKIN_ID, ethers.parseEther("1"));

    await expect(
      skinVault.connect(operator).burn(user.address, SKIN_ID, ethers.parseEther("1"))
    ).to.emit(skinVault, "TokensBurned").withArgs(user.address, SKIN_ID, ethers.parseEther("1"));
  });

  it("mint/burn на незарегистрированный скин — revert", async function () {
    await expect(
      skinVault.connect(operator).mint(user.address, "Unknown Skin", ethers.parseEther("1"))
    ).to.be.revertedWith("Skin not registered");
  });
});
