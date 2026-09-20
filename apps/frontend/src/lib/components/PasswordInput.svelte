<script lang="ts">
  import type { FullAutoFill } from "svelte/elements";
  import Icon from "./Icon.svelte";

  /**
   * Password field with a show/hide toggle.
   * Drop-in for a plain `<input class="input">`; everything else is
   * forwarded via `$$restProps` so `required`, `minlength`, `id`,
   * `autocomplete`, `aria-*`, etc. keep working. Use `bind:value`.
   */
  export let value = "";
  export let id: string | undefined = undefined;
  export let autocomplete: FullAutoFill | undefined = undefined;
  export let placeholder: string | undefined = undefined;
  export let disabled = false;

  let visible = false;
  $: type = visible ? "text" : "password";
</script>

<div class="password-field relative">
  <input
    {...$$restProps}
    {id}
    {disabled}
    {placeholder}
    {autocomplete}
    class="input pr-11 {$$restProps.class || ''}"
    {type}
    bind:value
  />
  <button
    type="button"
    class="password-toggle"
    aria-label={visible ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
    aria-pressed={visible}
    title={visible ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
    tabindex="-1"
    {disabled}
    on:click={() => (visible = !visible)}
  >
    <Icon name={visible ? "eye-slash" : "eye"} size="14px" />
  </button>
</div>
