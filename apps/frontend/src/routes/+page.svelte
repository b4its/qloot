<script lang="ts">
  import { auth } from "$lib/stores/auth";
  $: user = $auth.user;

  const features = [
    { icon: "📚", title: "Learning", desc: "Courses, lessons and AI-generated practice from your own PDFs." },
    { icon: "🎯", title: "Live Rooms", desc: "Join competitive rooms with real-time presence and leaderboards." },
    { icon: "📝", title: "AI Exams", desc: "Essay exams graded by AI with feedback and similarity scores." },
    { icon: "🏆", title: "Quests", desc: "Speed-based quests where the fastest valid winners earn OPC." },
    { icon: "📊", title: "Ranking", desc: "Global, room and quest leaderboards updated live." },
    { icon: "💎", title: "OPC Rewards", desc: "Earn OryphemCoin on-chain via ERC-1155 with full audit trail." },
  ];
</script>

<svelte:head><title>QLoot — Gamified Learning on Web3 + AI</title></svelte:head>

<section class="py-12 text-center">
  <h1 class="text-4xl font-extrabold tracking-tight sm:text-5xl">
    Learn. Compete. <span class="text-primary-600">Earn OPC.</span>
  </h1>
  <p class="mx-auto mt-4 max-w-2xl muted">
    QLoot blends gamified learning with AI-powered grading and blockchain rewards.
    Complete quests, beat the leaderboard, and receive OryphemCoin — every reward
    verifiable on-chain.
  </p>
  <div class="mt-6 flex justify-center gap-3">
    {#if user}
      <a href="/learning" class="btn-primary">Go to Learning</a>
      <a href="/quests" class="btn-ghost">Browse Quests</a>
    {:else}
      <a href="/register" class="btn-primary">Get started</a>
      <a href="/login" class="btn-ghost">Sign in</a>
    {/if}
  </div>
</section>

<section class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
  {#each features as f}
    <div class="card">
      <div class="text-2xl" aria-hidden="true">{f.icon}</div>
      <h3 class="mt-2 font-semibold">{f.title}</h3>
      <p class="mt-1 text-sm muted">{f.desc}</p>
    </div>
  {/each}
</section>

<section class="card mt-8">
  <h2 class="text-lg font-semibold">Transparent on-chain rewards</h2>
  <p class="mt-1 text-sm muted">
    All asset and reward activity is recorded through blockchain transactions and
    events, while learning data and personal information stay off-chain. Treasury
    holds OPC on-chain; your balance lives in a double-entry ledger you can
    reconcile at any time — and withdraw to a personal wallet.
  </p>
</section>
