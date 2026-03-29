const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying with:", deployer.address);

  const OPERATOR_ADDRESS = process.env.OPERATOR_ADDRESS || deployer.address;

  const SkinVault = await ethers.getContractFactory("SkinVault");
  const vault = await SkinVault.deploy(OPERATOR_ADDRESS);
  await vault.waitForDeployment();

  const vaultAddress = await vault.getAddress();
  console.log("SkinVault deployed to:", vaultAddress);
  console.log("\nДобавь в .env:");
  console.log(`SKIN_VAULT_ADDRESS=${vaultAddress}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
