<script lang="ts">
  import { onMount } from "svelte";

  const links = [
    {
      href: "/dashboard",
      label: "Academic Dashboard",
      desc: "Your grades, trends and AI insights at a glance",
      icon: "📊",
    },
    {
      href: "/career/personality",
      label: "Big Five Test",
      desc: "Measure 5 personality traits (simulated BFI-2)",
      icon: "🧠",
    },
    {
      href: "/career/roadmap",
      label: "AI Analysis & Roadmap",
      desc: "Major recommendations and a milestone roadmap",
      icon: "🧭",
    },
    {
      href: "/career/consultation",
      label: "Counselling Room",
      desc: "Book BK sessions and approve analyses",
      icon: "🗓️",
    },
    {
      href: "/career/library",
      label: "Resource Library",
      desc: "Courses, clubs and study materials",
      icon: "📚",
    },
    {
      href: "/assistant",
      label: "AI Assistant",
      desc: "Ask about majors, campuses and careers",
      icon: "🤖",
    },
  ];

  onMount(() => {});
</script>

<svelte:head><title>Career Guidance — QLoot</title></svelte:head>

<h1 class="text-2xl font-bold">Career Guidance</h1>
<p class="mt-1 muted">
  A simulated pathway planner: academic insights, personality profiling, AI major recommendations, a
  milestone roadmap and counselling — all inside QLoot.
</p>

<div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
  {#each links as l}
    <a href={l.href} class="card block transition hover:border-primary-400">
      <div class="text-2xl" aria-hidden="true">{l.icon}</div>
      <h2 class="mt-1 font-semibold">{l.label}</h2>
      <p class="text-sm muted">{l.desc}</p>
    </a>
  {/each}
</div>
