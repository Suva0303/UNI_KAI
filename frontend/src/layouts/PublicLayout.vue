<template>
  <div class="min-h-screen bg-page-mist text-charcoal">
    <header class="border-b border-matte-lilac/80 bg-white/90 backdrop-blur-md">
      <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <router-link to="/" class="text-2xl font-bold text-[#5e4b7a]">UNI</router-link>
        <nav class="flex items-center gap-4">
          <router-link to="/about" class="rounded-full px-3 py-1.5 text-sm hover:bg-matte-blue/50">О проекте</router-link>
          <router-link
            to="/admin/login"
            class="rounded-full border border-matte-lilac bg-white px-4 py-2 text-sm font-medium text-[#5e4b7a] hover:bg-matte-dust/60"
          >
            Вход для администратора
          </router-link>
        </nav>
      </div>
    </header>
    <main class="mx-auto max-w-7xl px-6 py-8">
      <router-view />
    </main>
  </div>
</template>
