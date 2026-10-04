<script lang="ts">
  import { api, ApiError } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";

  interface ForgotResponse {
    message: string;
    reset_token?: string | null;
  }

  let email = "";
  let sent = false;
  let loading = false;
  let error = "";
  let resetToken: string | null = null;

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  let emailValid = false;
  $: emailValid = EMAIL_RE.test(email.trim());

  async function submit(e: Event) {
    e.preventDefault();
    error = "";
    // Never hit the network with an empty/invalid email: show why instead.
    if (!emailValid) {
      error = "Masukkan alamat email yang valid.";
      return;
    }
    loading = true;
    try {
      const res = await api.post<ForgotResponse>("/auth/forgot-password", {
        email: email.trim(),
      });
      resetToken = res.reset_token ?? null;
      sent = true;
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Gagal mengirim permintaan reset";
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Lupa Sandi | QLoot</title></svelte:head>

<div class="relative grid min-h-[80vh] place-items-center overflow-hidden px-4 py-12">
  <div class="aurora"></div>
  <div class="relative z-10 w-full max-w-md">
    <div class="grad-border">
      <div class="card !p-7">
        <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
          <Icon name="key" size="18px" />
        </span>
        <h1 class="mt-4 font-display text-2xl font-bold">Atur ulang kata sandi</h1>
        {#if error}
          <p class="alert-error mt-4" role="alert" aria-live="assertive">{error}</p>
        {/if}
        {#if sent}
          <p class="alert-ok mt-4" role="status" aria-live="polite">
            Jika akun dengan email tersebut ada, tautan reset telah dikirim.
          </p>
          {#if resetToken}
            <div class="card mt-4 !p-4">
              <p class="mono-label text-amber-400">Mode pengembangan</p>
              <p class="mt-1 text-xs muted">
                Tidak ada email sungguhan yang dikirim pada mode ini. Token di bawah hanya untuk
                pengujian: jangan bagikan ke siapa pun.
              </p>
              <div class="mono mt-2 break-all rounded-sm border px-3 py-2 text-xs">
                {resetToken}
              </div>
              <a
                href={`/reset-password?token=${encodeURIComponent(resetToken)}`}
                class="btn-primary mt-3 w-full"
                ><Icon name="arrow-right" size="12px" /> Lanjut atur ulang sandi</a
              >
            </div>
          {/if}
        {:else}
          <p class="mt-1 text-sm muted">Masukkan emailmu dan kami akan mengirim instruksi reset.</p>
          <form class="mt-5 space-y-4" on:submit={submit}>
            <div>
              <label class="mono-label" for="email">Email</label>
              <input
                id="email"
                class="input mt-1"
                type="email"
                bind:value={email}
                required
                aria-invalid={email.length > 0 && !emailValid}
              />
              {#if email.length > 0 && !emailValid}
                <span class="mt-1 block text-[11px] text-danger">Format email belum valid.</span>
              {/if}
            </div>
            <button class="btn-primary w-full" type="submit" disabled={loading || !emailValid}>
              {#if loading}<Icon name="spinner" spin size="13px" />{:else}<Icon
                  name="paper-plane"
                  size="13px"
                />{/if}
              {loading ? "Mengirim…" : "Kirim tautan reset"}
            </button>
          </form>
        {/if}
        <p class="mt-5 text-center text-sm muted">
          <a href="/login" class="text-primary hover:underline">Kembali ke masuk</a>
        </p>
      </div>
    </div>
  </div>
</div>
