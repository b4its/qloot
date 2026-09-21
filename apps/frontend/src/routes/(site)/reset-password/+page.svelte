<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  let token = "";
  let password = "";
  let confirm = "";
  let loading = false;
  let done = false;
  let error = "";

  onMount(() => {
    token = $page.url.searchParams.get("token") ?? "";
  });

  function validate(): string | null {
    if (token.trim().length < 8) return "Token reset tidak valid. Minta tautan baru.";
    if (password.length < 8) return "Kata sandi minimal 8 karakter.";
    if (password !== confirm) return "Konfirmasi kata sandi tidak sama.";
    return null;
  }

  async function submit(e: Event) {
    e.preventDefault();
    error = "";
    const v = validate();
    if (v) {
      error = v;
      return;
    }
    loading = true;
    try {
      await api.post("/auth/reset-password", { token: token.trim(), new_password: password });
      done = true;
      setTimeout(() => goto("/login"), 1800);
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Gagal mengatur ulang kata sandi";
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Atur Ulang Sandi — QLoot</title></svelte:head>

<div class="relative grid min-h-[80vh] place-items-center overflow-hidden px-4 py-12">
  <div class="aurora"></div>
  <div class="relative z-10 w-full max-w-md">
    <div class="grad-border">
      <div class="card !p-7">
        <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
          <Icon name="lock" size="18px" />
        </span>
        <h1 class="mt-4 font-display text-2xl font-bold">Kata sandi baru</h1>

        {#if error}
          <p class="alert-error mt-4">{error}</p>
        {/if}

        {#if done}
          <p class="alert-ok mt-4">Kata sandi berhasil diperbarui. Mengalihkan ke halaman masuk…</p>
        {:else}
          <p class="mt-1 text-sm muted">Masukkan kata sandi baru untuk akunmu.</p>
          <form class="mt-5 space-y-4" on:submit={submit}>
            <div>
              <label class="mono-label" for="token">Token reset</label>
              <input id="token" class="input font-mono mt-1" bind:value={token} required />
            </div>
            <div>
              <label class="mono-label" for="password">Kata sandi baru</label>
              <PasswordInput
                id="password"
                class="mt-1"
                bind:value={password}
                required
                minlength="8"
                autocomplete="new-password"
              />
            </div>
            <div>
              <label class="mono-label" for="confirm">Konfirmasi kata sandi</label>
              <PasswordInput
                id="confirm"
                class="mt-1"
                bind:value={confirm}
                required
                autocomplete="new-password"
              />
            </div>
            <button class="btn-primary w-full" type="submit" disabled={loading}>
              {#if loading}<Icon name="spinner" spin size="13px" />{:else}<Icon
                  name="check"
                  size="13px"
                />{/if}
              {loading ? "Menyimpan…" : "Simpan kata sandi"}
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
