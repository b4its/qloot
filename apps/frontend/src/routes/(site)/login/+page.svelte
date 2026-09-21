<script lang="ts">
  import { goto } from "$app/navigation";
  import { auth } from "$lib/stores/auth";
  import { ApiError } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  let email = "";
  let password = "";
  let error = "";
  let loading = false;

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
</script>

<svelte:head><title>Masuk — QLoot</title></svelte:head>

<div class="relative grid min-h-[80vh] place-items-center overflow-hidden px-4 py-12">
  <div class="aurora"></div>
  <div class="relative z-10 w-full max-w-md">
    <div class="grad-border">
      <div class="card !p-7">
        <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
          <Icon name="right-to-bracket" size="18px" />
        </span>
        <h1 class="mt-4 font-display text-2xl font-bold">Selamat datang kembali</h1>
        <p class="mt-1 text-sm muted">Masuk untuk melanjutkan perjalanan belajarmu.</p>

        {#if error}
          <p class="alert-error mt-4" role="alert">
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
            <PasswordInput
              id="password"
              class="mt-1"
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

        <p class="mt-5 text-center text-sm muted">
          Belum punya akun? <a href="/register" class="text-primary hover:underline">Daftar</a>
          · <a href="/forgot-password" class="text-primary hover:underline">Lupa sandi?</a>
        </p>
      </div>
    </div>
  </div>
</div>
