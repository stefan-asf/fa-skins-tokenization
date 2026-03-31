const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying with:", deployer.address);

  const SkinToken = await ethers.getContractFactory("SkinToken");
  const token = await SkinToken.deploy(
    "P250 Sand Dune",
    "P250SD",
    deployer.address  // оператор = бэкенд-кошелёк
  );
  await token.waitForDeployment();

  const address = await token.getAddress();
  console.log("SkinToken deployed to:", address);
  console.log("\nДобавь в .env на сервере:");
  console.log(`SKIN_TOKEN_ADDRESS=${address}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
