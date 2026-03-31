import { t } from "./i18n/index.js";
import { api } from "./api.js";

export async function connectMetaMask() {
  if (!window.ethereum) throw new Error(t("errors.metamask_not_found"));
  const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
  const address = accounts[0];
  await api.setWallet(address);
  return address;
}

export function getConnectedAccount() {
  if (!window.ethereum) return null;
  const accounts = window.ethereum.selectedAddress;
  return accounts || null;
}
