/**
 * Minimal MetaMask / EIP-1193 helper.
 *
 * We deliberately avoid pulling in ethers/wagmi: the only thing we need is the
 * user's account address, which `eth_requestAccounts` returns directly. This
 * keeps the frontend dependency-free and works with any injected provider.
 */

interface Eip1193Provider {
  request: (args: { method: string; params?: unknown[] | object }) => Promise<unknown>;
  isMetaMask?: boolean;
  on?: (event: string, handler: (...args: unknown[]) => void) => void;
  removeListener?: (event: string, handler: (...args: unknown[]) => void) => void;
}

declare global {
  interface Window {
    ethereum?: Eip1193Provider;
  }
}

/** True when an injected wallet (MetaMask, etc.) is available. */
export function hasInjectedWallet(): boolean {
  return typeof window !== "undefined" && !!window.ethereum?.request;
}

/**
 * Prompt the user to connect and return the selected account address.
 * Throws a friendly Error when there is no provider or the user rejects.
 */
export async function connectWalletAddress(): Promise<string> {
  const provider = typeof window !== "undefined" ? window.ethereum : undefined;
  if (!provider?.request) {
    throw new Error("MetaMask tidak terdeteksi. Pasang ekstensi MetaMask dulu.");
  }
  try {
    const accounts = (await provider.request({ method: "eth_requestAccounts" })) as string[];
    const address = accounts?.[0];
    if (!address) throw new Error("Tidak ada akun yang terhubung di MetaMask.");
    return address;
  } catch (err) {
    // EIP-1193: user rejection carries code 4001.
    const code = (err as { code?: number })?.code;
    if (code === 4001) throw new Error("Permintaan koneksi dibatalkan.");
    throw err instanceof Error ? err : new Error("Gagal menghubungkan MetaMask.");
  }
}
