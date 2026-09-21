/** Basis-point helpers. Scores are stored as integer basis points (10000 = 100%). */
export const BP_SCALE = 10_000;

/** Slice an in-memory list into a single page (1-indexed). For lists that are
 * fetched in full and/or filtered client-side, where offset math on the server
 * cannot be applied to the filtered set. Pair with `<Pagination {total} />`. */
export function paginate<T>(items: T[], page: number, pageSize: number): T[] {
  const start = Math.max(0, (page - 1) * pageSize);
  return items.slice(start, start + pageSize);
}

export function bpToPercent(bp: number | null | undefined, digits = 1): string {
  if (bp === null || bp === undefined) return "—";
  return `${(bp / 100).toFixed(digits)}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("id-ID", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const sec = Math.round(diff / 1000);
  if (Math.abs(sec) < 60) return `${sec} dtk lalu`;
  const min = Math.round(sec / 60);
  if (Math.abs(min) < 60) return `${min} mnt lalu`;
  const hr = Math.round(min / 60);
  if (Math.abs(hr) < 24) return `${hr} jam lalu`;
  const day = Math.round(hr / 24);
  if (Math.abs(day) < 30) return `${day} hari lalu`;
  const month = Math.round(day / 30);
  if (Math.abs(month) < 12) return `${month} bln lalu`;
  return `${Math.round(month / 12)} thn lalu`;
}

export function shortHash(hash: string | null | undefined, size = 6): string {
  if (!hash) return "—";
  return `${hash.slice(0, size)}…${hash.slice(-4)}`;
}

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "0";
  return new Intl.NumberFormat().format(n);
}

/** Human-readable Indonesian label for an internal status value. */
const STATUS_LABELS: Record<string, string> = {
  draft: "Draf",
  open: "Terbuka",
  published: "Terbit",
  finalized: "Final",
  closed: "Ditutup",
  completed: "Selesai",
  active: "Aktif",
  archived: "Diarsipkan",
  pending: "Menunggu",
  confirmed: "Terkonfirmasi",
  failed: "Gagal",
  queued: "Dalam antrean",
  created: "Dibuat",
  requested: "Diminta",
  processing: "Diproses",
  uploaded: "Terunggah",
  ready: "Siap",
  not_started: "Belum dimulai",
  in_progress: "Berjalan",
  started: "Dimulai",
  submitted: "Terkumpul",
  grading: "Dinilai",
  graded: "Ternilai",
  grading_failed: "Gagal dinilai",
  new: "Baru",
  done: "Selesai",
  approved: "Disetujui",
  in_review: "Dalam tinjauan",
  rejected: "Ditolak",
  mastered: "Dikuasai",
};

/** Map an internal English status to its Indonesian display label. */
export function statusLabel(status: string | null | undefined): string {
  if (!status) return "—";
  return STATUS_LABELS[status.toLowerCase()] ?? status;
}

export function etherscanUrl(txHash: string | null | undefined, chainId = 11155111): string | null {
  if (!txHash) return null;
  if (chainId === 11155111) return `https://sepolia.etherscan.io/tx/${txHash}`;
  return null;
}
