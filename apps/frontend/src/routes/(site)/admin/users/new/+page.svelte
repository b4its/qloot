<script lang="ts">
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { User } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";

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

  async function createUser() {
    error = "";
    message = "";
    creating = true;
    try {
      const payload = {
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        password: form.password,
        role: form.role,
        class_code: form.class_code.trim() || null,
        class_type: form.class_type.trim() || null,
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

  <div class="card mt-6">
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="block sm:col-span-2">
        <span class="mono-label">Email</span>
        <input
          class="input mt-1"
          type="email"
          placeholder="nama@qloot.example"
          bind:value={form.email}
        />
      </label>
      <label class="block sm:col-span-2">
        <span class="mono-label">Nama lengkap</span>
        <input class="input mt-1" placeholder="Nama lengkap" bind:value={form.full_name} />
      </label>
      <label class="block">
        <span class="mono-label">Kata sandi</span>
        <input
          class="input mt-1"
          type="password"
          placeholder="min. 8 karakter"
          bind:value={form.password}
        />
      </label>
      <label class="block">
        <span class="mono-label">Peran</span>
        <select class="input mt-1" bind:value={form.role}>
          <option value="student">Siswa</option>
          <option value="teacher">Guru</option>
          <option value="admin">Admin</option>
        </select>
      </label>
      <label class="block">
        <span class="mono-label">Kelas (opsional)</span>
        <input class="input mt-1" placeholder="mis. 1A" bind:value={form.class_code} />
      </label>
      <label class="block">
        <span class="mono-label">Tipe kelas (opsional)</span>
        <input class="input mt-1" placeholder="mis. IPA" bind:value={form.class_type} />
      </label>
    </div>
  </div>

  <div class="mt-4 flex items-center justify-end gap-2">
    <a href="/admin/users" class="btn-ghost">Batal</a>
    <button
      class="btn-primary"
      on:click={createUser}
      disabled={creating ||
        form.email.trim().length < 3 ||
        form.full_name.trim().length < 2 ||
        form.password.length < 8}
    >
      {#if creating}<Icon name="spinner" spin size="12px" />{:else}<Icon
          name="plus"
          size="12px"
        />{/if}
      Buat akun
    </button>
  </div>
</div>
