<template>
  <div class="min-h-screen bg-page-mist text-charcoal">
    <AppHeader />
    <main class="mx-auto w-full max-w-7xl px-4 py-6 md:px-6">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import AppHeader from "../components/layout/AppHeader.vue";
</script>
