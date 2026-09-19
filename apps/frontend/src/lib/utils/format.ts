/** Basis-point helpers. Scores are stored as integer basis points (10000 = 100%). */
export const BP_SCALE = 10_000;

export function bpToPercent(bp: number | null | undefined, digits = 1): string {
  if (bp === null || bp === undefined) return "—";
  return `${(bp / 100).toFixed(digits)}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const sec = Math.round(diff / 1000);
  if (Math.abs(sec) < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (Math.abs(min) < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (Math.abs(hr) < 24) return `${hr}h ago`;
  return `${Math.round(hr / 24)}d ago`;
}

export function shortHash(hash: string | null | undefined, size = 6): string {
  if (!hash) return "—";
  return `${hash.slice(0, size)}…${hash.slice(-4)}`;
}

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "0";
  return new Intl.NumberFormat().format(n);
}

export function etherscanUrl(txHash: string | null | undefined, chainId = 11155111): string | null {
  if (!txHash) return null;
  if (chainId === 11155111) return `https://sepolia.etherscan.io/tx/${txHash}`;
  return null;
}
