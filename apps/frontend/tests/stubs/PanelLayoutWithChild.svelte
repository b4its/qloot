<script lang="ts">
  // Test-only wrapper: puts a marker in the panel layout's default slot so the
  // test can assert whether the child page is mounted yet.
  import PanelLayout from "$routes-panel/+layout.svelte";
</script>

<PanelLayout>
  <div data-test-marker>CHILD</div>
</PanelLayout>
