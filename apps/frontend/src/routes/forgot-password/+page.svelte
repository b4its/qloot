<script lang="ts">
  import { api } from "$lib/api/client";

  let email = "";
  let sent = false;
  let loading = false;

  async function submit(e: Event) {
    e.preventDefault();
    loading = true;
    try {
      await api.post("/auth/forgot-password", { email });
      sent = true;
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Forgot password — QLoot</title></svelte:head>

<div class="mx-auto max-w-md py-10">
  <div class="card">
    <h1 class="text-xl font-semibold">Reset your password</h1>
    {#if sent}
      <p
        class="mt-4 rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-950 dark:text-green-200"
      >
        If an account exists for that email, a reset link has been sent.
      </p>
    {:else}
      <p class="mt-1 text-sm muted">Enter your email and we'll send reset instructions.</p>
      <form class="mt-5 space-y-4" on:submit={submit}>
        <div>
          <label class="mb-1 block text-sm font-medium" for="email">Email</label>
          <input id="email" class="input" type="email" bind:value={email} required />
        </div>
        <button class="btn-primary w-full" type="submit" disabled={loading}>
          {loading ? "Sending…" : "Send reset link"}
        </button>
      </form>
    {/if}
    <p class="mt-4 text-center text-sm muted">
      <a href="/login" class="text-primary-600">Back to sign in</a>
    </p>
  </div>
</div>
