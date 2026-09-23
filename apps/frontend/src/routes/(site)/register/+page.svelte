<script lang="ts">
  import { goto } from "$app/navigation";
  import { auth } from "$lib/stores/auth";
  import { ApiError } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  let email = "";
  let full_name = "";
  let password = "";
  let class_code = "1A";
  let class_type = "IPA";
  let error = "";
  let loading = false;

  const classTypes = ["IPA", "IPS", "Bahasa", "Umum"];

  function validate(): string | null {
    if (full_name.trim().length < 2) return "Nama minimal 2 karakter.";
    if (password.length < 8) return "Kata sandi minimal 8 karakter.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return "Masukkan email yang valid.";
    if (class_code.trim().length < 1) return "Masukkan kelasmu (mis. 1A).";
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
      await auth.register({
        email,
        full_name,
        password,
        role: "student",
        class_code,
        class_type,
      });
      await goto("/dashboard");
    } catch (err) {
      error = err instanceof ApiError ? err.message : "Registrasi gagal";
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Daftar — QLoot</title></svelte:head>

<div class="relative grid min-h-[80vh] place-items-center overflow-hidden px-4 py-12">
  <div class="aurora"></div>
  <div class="relative z-10 w-full max-w-md">
    <div class="grad-border">
      <div class="card !p-7">
        <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
          <Icon name="rocket" size="18px" />
        </span>
        <h1 class="mt-4 font-display text-2xl font-bold">Mulai perjalananmu</h1>
        <p class="mt-1 text-sm muted">Gratis. Tanpa kartu kredit. Sertifikat digital menanti.</p>

        {#if error}
          <p class="alert-error mt-4" role="alert">
            {error}
          </p>
        {/if}

        <form class="mt-5 space-y-4" on:submit={submit}>
          <div>
            <label class="mono-label" for="name">Nama lengkap</label>
            <input
              id="name"
              class="input mt-1"
              bind:value={full_name}
              required
              autocomplete="name"
            />
          </div>
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
              minlength="8"
              autocomplete="new-password"
            />
          </div>
          <div>
            <label class="mono-label" for="class_code">Kelas</label>
            <input
              id="class_code"
              class="input mt-1"
              placeholder="mis. 1A"
              bind:value={class_code}
              required
            />
          </div>
          <div>
            <label class="mono-label" for="class_type">Tipe kelas</label>
            <select id="class_type" class="input mt-1" bind:value={class_type}>
              {#each classTypes as t}<option value={t}>{t}</option>{/each}
            </select>
          </div>
          <p class="muted text-xs">
            <Icon name="circle-info" size="10px" /> Kamu akan melihat pelajaran untuk kelas {class_code ||
              "—"}. Akun guru dibuat oleh admin.
          </p>
          <button class="btn-primary w-full" type="submit" disabled={loading}>
            {#if loading}<Icon name="spinner" spin size="13px" />{:else}<Icon
                name="user-plus"
                size="13px"
              />{/if}
            {loading ? "Membuat akun…" : "Daftar"}
          </button>
        </form>

        <p class="mt-5 text-center text-sm muted">
          Sudah punya akun? <a href="/login" class="text-primary hover:underline">Masuk</a>
        </p>
      </div>
    </div>
  </div>
</div>
