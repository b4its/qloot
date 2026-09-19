<script lang="ts">
  import { goto } from "$app/navigation";
  import { auth } from "$lib/stores/auth";
  import { ApiError } from "$lib/api/client";

  let email = "";
  let full_name = "";
  let password = "";
  let role = "student";
  let error = "";
  let loading = false;

  function validate(): string | null {
    if (full_name.trim().length < 2) return "Full name must be at least 2 characters.";
    if (password.length < 8) return "Password must be at least 8 characters.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return "Enter a valid email address.";
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
      await auth.register({ email, full_name, password, role });
      await goto("/learning");
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Registration failed";
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Sign up — QLoot</title></svelte:head>

<div class="mx-auto max-w-md py-10">
  <div class="card">
    <h1 class="text-xl font-semibold">Create your account</h1>
    <p class="mt-1 text-sm muted">Start learning, compete and earn OryphemCoin.</p>

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
        <label class="mb-1 block text-sm font-medium" for="name">Full name</label>
        <input id="name" class="input" bind:value={full_name} required autocomplete="name" />
      </div>
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
          minlength="8"
          autocomplete="new-password"
        />
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium" for="role">I am a</label>
        <select id="role" class="input" bind:value={role}>
          <option value="student">Student</option>
          <option value="teacher">Teacher</option>
        </select>
        <p class="mt-1 text-xs muted">Admins are created by the platform.</p>
      </div>
      <button class="btn-primary w-full" type="submit" disabled={loading}>
        {loading ? "Creating…" : "Create account"}
      </button>
    </form>

    <p class="mt-4 text-center text-sm muted">
      Already registered? <a href="/login" class="text-primary-600">Sign in</a>
    </p>
  </div>
</div>
