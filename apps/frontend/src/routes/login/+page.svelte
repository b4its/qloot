<script lang="ts">
  import { goto } from "$app/navigation";
  import { auth } from "$lib/stores/auth";
  import { ApiError } from "$lib/api/client";

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
      await goto("/learning");
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Login failed";
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Login — QLoot</title></svelte:head>

<div class="mx-auto max-w-md py-10">
  <div class="card">
    <h1 class="text-xl font-semibold">Welcome back</h1>
    <p class="mt-1 text-sm muted">Sign in to continue learning and earning OPC.</p>

    {#if error}
      <p
        class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-200"
        role="alert"
      >
        {error}
      </p>
    {/if}

    <form class="mt-5 space-y-4" on:submit={submit}>
      <div>
        <label class="mb-1 block text-sm font-medium" for="email">Email</label>
        <input
          id="email"
          class="input"
          type="email"
          bind:value={email}
          required
          autocomplete="email"
        />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium" for="password">Password</label>
        <input
          id="password"
          class="input"
          type="password"
          bind:value={password}
          required
          autocomplete="current-password"
        />
      </div>
      <button class="btn-primary w-full" type="submit" disabled={loading}>
        {loading ? "Signing in…" : "Sign in"}
      </button>
    </form>

    <p class="mt-4 text-center text-sm muted">
      No account? <a href="/register" class="text-primary-600">Create one</a>
      · <a href="/forgot-password" class="text-primary-600">Forgot password?</a>
    </p>
  </div>
</div>
