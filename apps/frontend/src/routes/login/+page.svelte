<script lang="ts">
  import { goto } from "$app/navigation";
  import { auth } from "$lib/stores/auth";
  import { ApiError } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";

  let email = "";
  let password = "";
  let error = "";
  let loading = false;
  let walletBusy = false;

  async function submit(e: Event) {
    e.preventDefault();
    error = "";
    loading = true;
    try {
      await auth.login(email, password);
      await goto("/dashboard");
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Gagal masuk";
    } finally {
      loading = false;
    }
  }

  async function walletLogin() {
    // Web3 gimmick: simulate a wallet signature flow.
    walletBusy = true;
    error = "";
    await new Promise((r) => setTimeout(r, 900));
    walletBusy = false;
    error = "Masuk dengan Wallet belum tersedia di demo ini. Gunakan email untuk mencoba.";
  }
</script>

<svelte:head><title>Masuk — QLoot</title></svelte:head>

<div class="relative grid min-h-[80vh] place-items-center overflow-hidden px-4 py-12">
  <div class="aurora"></div>
  <div class="relative z-10 w-full max-w-md">
    <div class="grad-border">
      <div class="card !p-7">
        <span
          class="grid h-11 w-11 place-items-center rounded-xl text-white"
          style="background-image:linear-gradient(135deg,#5B48FF,#00E5A8)"
        >
          <Icon name="right-to-bracket" size="18px" />
        </span>
        <h1 class="mt-4 font-display text-2xl font-bold">Selamat datang kembali</h1>
        <p class="mt-1 text-sm muted">Masuk untuk melanjutkan perjalanan belajarmu.</p>

        {#if error}
          <p class="mt-4 rounded-sm bg-tertiary/10 p-3 text-sm text-tertiary" role="alert">
            {error}
          </p>
        {/if}

        <form class="mt-5 space-y-4" on:submit={submit}>
          <div>
            <label class="mono-label" for="email">Email</label>
            <input
              id="email"
              class="input mt-1"
              type="email"
              bind:value={email}
              required
              autocomplete="email"
            />
          </div>
          <div>
            <label class="mono-label" for="password">Kata sandi</label>
            <input
              id="password"
              class="input mt-1"
              type="password"
              bind:value={password}
              required
              autocomplete="current-password"
            />
          </div>
          <button class="btn-primary w-full" type="submit" disabled={loading}>
            {#if loading}<Icon name="spinner" spin size="13px" />{:else}<Icon
                name="arrow-right-to-bracket"
                size="13px"
              />{/if}
            {loading ? "Memproses…" : "Masuk"}
          </button>
        </form>

        <div class="my-5 flex items-center gap-3 text-xs muted">
          <span class="h-px flex-1 bg-line"></span> atau <span class="h-px flex-1 bg-line"></span>
        </div>

        <button class="btn-secondary w-full" on:click={walletLogin} disabled={walletBusy}>
          {#if walletBusy}<Icon name="spinner" spin size="13px" />{:else}<Icon
              name="wallet"
              size="13px"
            />{/if}
          Masuk dengan Wallet
        </button>

        <p class="mt-5 text-center text-sm muted">
          Belum punya akun? <a href="/register" class="text-primary hover:underline">Daftar</a>
          · <a href="/forgot-password" class="text-primary hover:underline">Lupa sandi?</a>
        </p>
      </div>
    </div>
  </div>
</div>
