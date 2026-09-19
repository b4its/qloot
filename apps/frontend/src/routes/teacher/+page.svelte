<script lang="ts">
  import { auth, hasRole } from "$lib/stores/auth";
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";

  onMount(() => {
    if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");
  });

  const links = [
    { href: "/teacher/materials", label: "Materials", desc: "Upload PDFs and generate questions with AI", icon: "📄" },
    { href: "/teacher/exams", label: "Exams", desc: "Create exams, review AI questions, publish", icon: "📝" },
    { href: "/teacher/quests", label: "Quests", desc: "Set reward rules and finalize winners", icon: "🏆" },
    { href: "/teacher/rankings", label: "Rankings", desc: "Inspect leaderboards", icon: "📊" },
  ];
</script>

<svelte:head><title>Teacher — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Teacher Dashboard</h1>
<p class="mt-1 muted">Create materials, generate questions with AI, run exams and quests.</p>

<div class="mt-6 grid gap-4 sm:grid-cols-2">
  {#each links as l}
    <a href={l.href} class="card block transition hover:border-primary-400">
      <div class="text-2xl" aria-hidden="true">{l.icon}</div>
      <h2 class="mt-1 font-semibold">{l.label}</h2>
      <p class="text-sm muted">{l.desc}</p>
    </a>
  {/each}
</div>
