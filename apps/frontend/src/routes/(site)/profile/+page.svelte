<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError, API_BASE } from "$lib/api/client";
  import type { GamificationProfile, SessionInfo } from "$lib/types";
  import { auth } from "$lib/stores/auth";
  import { formatDate, formatNumber } from "$lib/utils/format";
  import Icon from "$lib/components/Icon.svelte";
  import WalletChip from "$lib/components/WalletChip.svelte";

  let sessions: SessionInfo[] = [];
  let profile: GamificationProfile | null = null;
  let loading = true;
  let error = "";
  let revoking = "";
  let signingOutAll = false;
  let currentPassword = "";
  let newPassword = "";
  let changingPassword = false;
  let passwordMessage = "";
  let passwordError = "";
  let editingName = false;
  let nameDraft = "";
  let savingName = false;
  let uploadingAvatar = false;
  let avatarError = "";
  let newEmail = "";
  let emailMessage = "";
  let emailError = "";
  let requestingEmailChange = false;
  // Simulation mode: the backend returns the change token when not in
  // production (no email transport), so the change can be completed in-session.
  let emailChangeToken: string | null = null;
  let pendingNewEmail = "";
  let confirmingEmailChange = false;
  // COMM-06: the caller's follower/following counts.
  let followCounts: { followers: number; following: number } | null = null;
  $: user = $auth.user;

  async function load() {
    loading = true;
    error = "";
    try {
      [sessions, profile] = await Promise.all([
        api.get<SessionInfo[]>("/auth/sessions"),
        api.get<GamificationProfile>("/gamification/me"),
      ]);
      if (user?.id) {
        followCounts = await api
          .get<{ followers: number; following: number }>(`/users/${user.id}/follow`)
          .catch(() => null);
      }
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat sesi";
    } finally {
      loading = false;
    }
  }

  async function revoke(id: string) {
    error = "";
    revoking = id;
    try {
      await api.delete(`/auth/sessions/${id}`);
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mencabut sesi";
    } finally {
      revoking = "";
    }
  }

  async function signOutEverywhere() {
    if (!confirm("Keluar dari semua perangkat? Kamu perlu masuk kembali di sini juga.")) return;
    error = "";
    signingOutAll = true;
    try {
      await auth.logoutAll();
      await goto("/login");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal keluar dari semua perangkat";
    } finally {
      signingOutAll = false;
    }
  }

  async function changePassword() {
    passwordError = "";
    passwordMessage = "";
    if (newPassword.length < 8) {
      passwordError = "Kata sandi baru minimal 8 karakter.";
      return;
    }
    changingPassword = true;
    try {
      await api.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      passwordMessage = "Kata sandi berhasil diganti. Sesi lain telah dikeluarkan.";
      currentPassword = "";
      newPassword = "";
      await load();
    } catch (e) {
      passwordError = e instanceof ApiError ? e.message : "Gagal mengganti kata sandi";
    } finally {
      changingPassword = false;
    }
  }

  function startEditName() {
    nameDraft = user?.full_name ?? "";
    editingName = true;
  }

  async function saveName() {
    if (nameDraft.trim().length < 1) return;
    savingName = true;
    error = "";
    try {
      const updated = await api.patch<{ full_name: string }>("/auth/profile", {
        full_name: nameDraft.trim(),
      });
      auth.setUser({ ...user, full_name: updated.full_name } as typeof user & object);
      editingName = false;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui nama";
    } finally {
      savingName = false;
    }
  }

  async function uploadAvatar(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    avatarError = "";
    uploadingAvatar = true;
    try {
      const form = new FormData();
      form.append("file", file);
      const updated = await api.post<{ avatar_url: string | null }>("/auth/profile/avatar", form);
      auth.setUser({ ...user, avatar_url: updated.avatar_url } as typeof user & object);
    } catch (err) {
      avatarError = err instanceof ApiError ? err.message : "Gagal mengunggah avatar";
    } finally {
      uploadingAvatar = false;
      input.value = "";
    }
  }

  async function requestEmailChange() {
    emailError = "";
    emailMessage = "";
    emailChangeToken = null;
    if (!newEmail.includes("@")) {
      emailError = "Masukkan alamat email yang valid.";
      return;
    }
    requestingEmailChange = true;
    try {
      const res = await api.post<{ message: string; change_token: string | null }>(
        "/auth/change-email/request",
        { new_email: newEmail },
      );
      pendingNewEmail = newEmail;
      // Outside production the verification token is returned so the change
      // can be confirmed in-session (mirrors the password-reset simulation).
      emailChangeToken = res.change_token ?? null;
      emailMessage = emailChangeToken
        ? "Mode simulasi: konfirmasi perubahan email di bawah."
        : "Tautan verifikasi telah dikirim ke email baru.";
      newEmail = "";
    } catch (e) {
      emailError = e instanceof ApiError ? e.message : "Gagal meminta perubahan email";
    } finally {
      requestingEmailChange = false;
    }
  }

  /** Confirm the pending email change with the returned token. */
  async function confirmEmailChange() {
    if (!emailChangeToken) return;
    emailError = "";
    emailMessage = "";
    confirmingEmailChange = true;
    try {
      const updated = await api.post<{ email: string }>("/auth/change-email/confirm", {
        token: emailChangeToken,
      });
      auth.setUser({ ...user, email: updated.email } as typeof user & object);
      emailChangeToken = null;
      emailMessage = `Email berhasil diubah menjadi ${updated.email}.`;
    } catch (e) {
      emailError = e instanceof ApiError ? e.message : "Gagal mengonfirmasi perubahan email";
    } finally {
      confirmingEmailChange = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Profil — QLoot</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-12 sm:px-6">
  {#if !user}
    <p class="muted">Silakan masuk terlebih dahulu.</p>
  {:else}
    <p class="mono-label">Akun</p>
    <h1 class="mt-1 font-display text-3xl font-bold">Profil</h1>

    <div class="mt-6 grad-border">
      <div class="card">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <label class="group relative cursor-pointer" title="Ganti avatar">
              {#if user.avatar_url}
                <img
                  src={`${API_BASE}/api/v1/auth/avatars/${user.id}`}
                  alt="Avatar"
                  class="h-14 w-14 rounded-sm object-cover"
                />
              {:else}
                <span
                  class="brand-mark grid h-14 w-14 place-items-center rounded-sm font-display text-lg font-bold"
                >
                  {user.full_name
                    .split(" ")
                    .map((n) => n[0])
                    .slice(0, 2)
                    .join("")}
                </span>
              {/if}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                class="sr-only"
                on:change={uploadAvatar}
                disabled={uploadingAvatar}
              />
              <span
                class="absolute -bottom-1 -right-1 grid h-5 w-5 place-items-center rounded-full bg-primary text-white opacity-0 transition-opacity group-hover:opacity-100"
              >
                <Icon name="camera" size="9px" />
              </span>
            </label>
            <div>
              {#if editingName}
                <div class="flex items-center gap-2">
                  <input class="input !py-1 text-sm" bind:value={nameDraft} />
                  <button class="btn-ghost !py-1" on:click={saveName} disabled={savingName}>
                    <Icon name="check" size="11px" />
                  </button>
                  <button class="btn-ghost !py-1" on:click={() => (editingName = false)}>
                    <Icon name="xmark" size="11px" />
                  </button>
                </div>
              {:else}
                <button
                  type="button"
                  class="flex items-center gap-2 font-display text-xl font-bold"
                  on:click={startEditName}
                >
                  {user.full_name}
                  <Icon name="pen" size="10px" class="text-tertiary" />
                </button>
              {/if}
              <p class="text-sm muted">{user.email}</p>
              {#if followCounts}
                <p class="mt-1 text-xs muted">
                  <strong>{followCounts.followers}</strong> pengikut ·
                  <strong>{followCounts.following}</strong> mengikuti
                </p>
              {/if}
            </div>
          </div>
          <WalletChip address={user.chain_user_ref} label="Wallet address" size={34} />
        </div>
        {#if avatarError}
          <p class="alert-error mt-2 text-xs">{avatarError}</p>
        {/if}

        <div class="mt-5 flex flex-wrap gap-2 border-t pt-5">
          {#each user.roles as r}
            <span class="badge badge-indigo"><Icon name="user-tag" size="10px" /> {r}</span>
          {/each}
          {#if user.class_code}
            <span class="badge badge-mint">
              <Icon name="chalkboard-user" size="10px" /> Kelas {user.class_code}{user.class_type
                ? ` · ${user.class_type}`
                : ""}
            </span>
          {/if}
          <span
            class="badge"
            class:badge-mint={user.is_active}
            class:badge-neutral={!user.is_active}
          >
            <Icon name={user.is_active ? "circle-check" : "circle-xmark"} size="10px" />
            {user.is_active ? "Aktif" : "Nonaktif"}
          </span>
        </div>
      </div>
    </div>

    {#if profile}
      <div class="mt-6 card">
        <div class="flex items-center justify-between">
          <h2 class="font-display font-bold">Progres gamifikasi</h2>
          <Icon name="ranking-star" size="14px" class="text-primary" />
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-6">
          <div>
            <p class="mono-label">Level</p>
            <p class="font-display text-3xl font-bold text-primary">{profile.level}</p>
          </div>
          <div>
            <p class="mono-label">Total XP</p>
            <p class="font-display text-3xl font-bold">{formatNumber(profile.xp)}</p>
          </div>
          <div class="min-w-[12rem] flex-1">
            <div class="flex items-center justify-between text-xs">
              <span class="muted">Menuju level {profile.level + 1}</span>
              <span class="mono"
                >{formatNumber(profile.xp_into_level)} / {formatNumber(
                  profile.xp_for_next_level,
                )}</span
              >
            </div>
            <div
              class="mt-2 h-2 w-full overflow-hidden rounded-full"
              style="background: rgb(var(--line))"
            >
              <div
                class="h-full rounded-full bg-primary transition-all"
                style={`width: ${Math.min(100, Math.max(0, profile.progress * 100))}%`}
              ></div>
            </div>
          </div>
        </div>
        <div class="mt-4 flex flex-wrap gap-2 border-t pt-4 text-xs">
          <span class="badge badge-indigo">Ujian {formatNumber(profile.breakdown.exams)} XP</span>
          <span class="badge badge-indigo">Quest {formatNumber(profile.breakdown.quests)} XP</span>
          <span class="badge badge-indigo">Tugas {formatNumber(profile.breakdown.tasks)} XP</span>
          <span class="badge badge-indigo">Badge {formatNumber(profile.breakdown.badges)} XP</span>
          <span class="badge badge-amber">
            <Icon name="fire" size="10px" /> Streak {profile.current_streak} hari
          </span>
          {#if profile.best_streak > profile.current_streak}
            <span class="badge badge-neutral">Terbaik {profile.best_streak} hari</span>
          {/if}
        </div>
      </div>
    {/if}

    <div class="mt-6 card">
      <div class="flex items-center justify-between">
        <h2 class="font-display font-bold">Ganti email</h2>
        <Icon name="envelope" size="14px" class="text-primary" />
      </div>
      {#if emailError}
        <p class="alert-error mt-3">{emailError}</p>
      {/if}
      {#if emailMessage}
        <p class="alert-ok mt-3">{emailMessage}</p>
      {/if}
      <div class="mt-3 flex flex-wrap items-end gap-2">
        <label class="block flex-1">
          <span class="mono-label">Email baru</span>
          <input class="input mt-1" type="email" bind:value={newEmail} />
        </label>
        <button
          class="btn-primary"
          on:click={requestEmailChange}
          disabled={requestingEmailChange || !newEmail}
        >
          {requestingEmailChange ? "Mengirim…" : "Kirim tautan verifikasi"}
        </button>
      </div>
      {#if emailChangeToken}
        <div class="mt-3 border-t pt-3">
          <p class="mono-label">Konfirmasi perubahan</p>
          <p class="mt-1 text-xs muted">
            Tidak ada email sungguhan yang dikirim (mode simulasi). Konfirmasi untuk mengubah email
            menjadi <strong>{pendingNewEmail}</strong>.
          </p>
          <button
            class="btn-primary mt-2 !py-1.5"
            on:click={confirmEmailChange}
            disabled={confirmingEmailChange}
          >
            {confirmingEmailChange ? "Memproses…" : "Konfirmasi perubahan email"}
          </button>
        </div>
      {/if}
    </div>

    <div class="mt-6 card">
      <div class="flex items-center justify-between">
        <h2 class="font-display font-bold">Ganti kata sandi</h2>
        <Icon name="key" size="14px" class="text-primary" />
      </div>
      {#if passwordError}
        <p class="alert-error mt-3">{passwordError}</p>
      {/if}
      {#if passwordMessage}
        <p class="alert-ok mt-3">{passwordMessage}</p>
      {/if}
      <div class="mt-3 grid gap-3 sm:grid-cols-2">
        <label class="block">
          <span class="mono-label">Kata sandi saat ini</span>
          <input class="input mt-1" type="password" bind:value={currentPassword} />
        </label>
        <label class="block">
          <span class="mono-label">Kata sandi baru</span>
          <input class="input mt-1" type="password" bind:value={newPassword} />
        </label>
      </div>
      <button
        class="btn-primary mt-3"
        on:click={changePassword}
        disabled={changingPassword || !currentPassword || newPassword.length < 8}
      >
        {changingPassword ? "Menyimpan…" : "Simpan kata sandi baru"}
      </button>
    </div>

    <div class="mt-6 card">
      <div class="flex items-center justify-between">
        <h2 class="font-display font-bold">Sesi aktif</h2>
        <Icon name="shield-halved" size="14px" class="text-primary" />
      </div>

      {#if error}
        <p class="alert-error mt-3">{error}</p>
      {/if}

      {#if loading}
        <div class="mt-3 space-y-2">
          {#each Array(2) as _}<div class="skeleton h-12"></div>{/each}
        </div>
      {:else if sessions.length === 0}
        <p class="mt-3 text-sm muted">Tidak ada sesi aktif lain.</p>
      {:else}
        <ul class="mt-3 divide-y">
          {#each sessions as s (s.id)}
            <li class="flex items-center justify-between gap-4 py-3">
              <div class="flex items-center gap-3">
                <Icon name="display" size="14px" class="muted" />
                <div>
                  <p class="text-sm">{s.user_agent?.slice(0, 48) ?? "Perangkat tidak dikenal"}</p>
                  <p class="text-xs muted">Sejak {formatDate(s.created_at)}</p>
                </div>
              </div>
              <button class="btn-ghost" on:click={() => revoke(s.id)} disabled={revoking === s.id}>
                {revoking === s.id ? "Mencabut…" : "Cabut"}
              </button>
            </li>
          {/each}
        </ul>
      {/if}

      <div class="mt-4 border-t pt-4">
        <button
          class="btn-ghost !text-tertiary"
          on:click={signOutEverywhere}
          disabled={signingOutAll}
        >
          <Icon name="right-from-bracket" size="12px" />
          {signingOutAll ? "Memproses…" : "Keluar dari semua perangkat"}
        </button>
      </div>
    </div>
  {/if}
</div>
