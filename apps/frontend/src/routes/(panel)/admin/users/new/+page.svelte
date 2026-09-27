<script lang="ts">
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { User } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  let form = {
    email: "",
    full_name: "",
    password: "",
    role: "student",
    class_code: "",
    class_type: "",
  };
  let creating = false;
  let error = "";
  let message = "";

  // --- inline validation -----------------------------------------------------
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  $: emailValid = EMAIL_RE.test(form.email.trim());
  $: nameValid = form.full_name.trim().length >= 2;
  $: passwordValid = form.password.length >= 8;
  // A simple, honest strength signal: length + character-class variety.
  $: passwordScore = (() => {
    const p = form.password;
    let s = 0;
    if (p.length >= 8) s++;
    if (p.length >= 12) s++;
    if (/[A-Z]/.test(p) && /[a-z]/.test(p)) s++;
    if (/\d/.test(p)) s++;
    if (/[^A-Za-z0-9]/.test(p)) s++;
    return Math.min(s, 4);
  })();
  $: passwordLabel = ["Sangat lemah", "Lemah", "Cukup", "Kuat", "Sangat kuat"][passwordScore];
  $: passwordTone = ["text-danger", "text-danger", "text-highlight", "text-mint", "text-mint"][
    passwordScore
  ];
  $: passwordBar = ["bg-danger", "bg-danger", "bg-highlight", "bg-mint", "bg-mint"][passwordScore];
  // Class targeting only applies to students.
  $: isStudent = form.role === "student";
  $: canSubmit = emailValid && nameValid && passwordValid && !creating;

  async function createUser() {
    if (!canSubmit) return;
    error = "";
    message = "";
    creating = true;
    try {
      const payload = {
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        password: form.password,
        role: form.role,
        class_code: isStudent ? form.class_code.trim() || null : null,
        class_type: isStudent ? form.class_type.trim() || null : null,
      };
      await api.post<User>("/admin/users", payload);
      message = `Akun ${payload.email} dibuat.`;
      await goto("/admin/users");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal membuat akun";
      creating = false;
    }
  }
</script>

<svelte:head><title>Tambah Pengguna — Admin — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Pengguna"
    title="Tambah pengguna"
    subtitle="Buat akun baru dengan peran apa pun. Siswa dapat diberi kelas dan tipe kelas."
    backHref="/admin/users"
    backLabel="Pengguna"
  />

  <PageAlerts {message} {error} />

  <form class="card mt-6" on:submit|preventDefault={createUser} aria-label="Form tambah pengguna">
    <p class="mono-label">Identitas</p>
    <div class="mt-2 grid gap-3 sm:grid-cols-2">
      <label class="block sm:col-span-2">
        <span class="mono-label">Email</span>
        <input
          class="input mt-1"
          type="email"
          placeholder="nama@qloot.example"
          bind:value={form.email}
          aria-invalid={form.email.length > 0 && !emailValid}
          required
        />
        {#if form.email.length > 0 && !emailValid}
          <span class="mt-1 block text-[11px] text-danger" data-role="email-hint">
            Format email belum benar.
          </span>
        {/if}
      </label>
      <label class="block sm:col-span-2">
        <span class="mono-label">Nama lengkap</span>
        <input class="input mt-1" placeholder="Nama lengkap" bind:value={form.full_name} required />
      </label>
    </div>

    <p class="mono-label mt-5">Kredensial & peran</p>
    <div class="mt-2 grid gap-3 sm:grid-cols-2">
      <label class="block">
        <span class="mono-label">Kata sandi</span>
        <PasswordInput
          class="mt-1"
          placeholder="min. 8 karakter"
          bind:value={form.password}
          autocomplete="new-password"
        />
        {#if form.password.length > 0}
          <span class="mt-1 flex items-center gap-2" data-role="password-strength">
            <span
              class="h-1.5 flex-1 overflow-hidden rounded-full"
              style="background: rgb(var(--line))"
            >
              <span
                class="block h-full rounded-full {passwordBar}"
                style={`width: ${(passwordScore / 4) * 100}%`}
              ></span>
            </span>
            <span class="text-[11px] {passwordTone}">{passwordLabel}</span>
          </span>
        {/if}
      </label>
      <label class="block">
        <span class="mono-label">Peran</span>
        <select class="input mt-1" bind:value={form.role}>
          <option value="student">Siswa</option>
          <option value="teacher">Guru</option>
          <option value="admin">Admin</option>
        </select>
      </label>
    </div>

    {#if isStudent}
      <p class="mono-label mt-5">Kelas (khusus siswa)</p>
      <div class="mt-2 grid gap-3 sm:grid-cols-2">
        <label class="block">
          <span class="mono-label">Kode kelas (opsional)</span>
          <input class="input mt-1" placeholder="mis. 1A" bind:value={form.class_code} />
        </label>
        <label class="block">
          <span class="mono-label">Tipe kelas (opsional)</span>
          <input class="input mt-1" placeholder="mis. IPA" bind:value={form.class_type} />
        </label>
      </div>
    {:else}
      <p class="mt-5 text-xs muted">
        Peran <strong>{form.role}</strong> tidak memerlukan penargetan kelas.
      </p>
    {/if}

    <div class="mt-5 flex items-center justify-end gap-2 border-t pt-4">
      <a href="/admin/users" class="btn-ghost">Batal</a>
      <button class="btn-primary" type="submit" disabled={!canSubmit}>
        {#if creating}<Icon name="spinner" spin size="12px" />{:else}<Icon
            name="plus"
            size="12px"
          />{/if}
        Buat akun
      </button>
    </div>
  </form>
</div>
