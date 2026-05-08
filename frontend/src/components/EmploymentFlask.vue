<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ percent: number }>();

const pct = computed(() => Math.min(100, Math.max(0, Number(props.percent) || 0)));
</script>

<template>
  <div
    class="mt-4 flex w-full max-w-full flex-col items-stretch gap-1"
    role="img"
    :aria-label="`Доля трудоустроенных ${pct.toFixed(1)}%`"
  >
    <div
      class="relative mx-auto w-[43.333333%] max-w-full shrink-0 overflow-hidden rounded-md border border-[#c9bfdc] bg-[#f0ecf8] aspect-[10/2]"
    >
      <div
        class="absolute inset-y-0 left-0 bg-emerald-500/90 transition-[width] duration-300"
        :style="{ width: `${pct}%` }"
      />
    </div>
    <span class="text-center text-[11.7px] font-semibold tabular-nums text-charcoal/75">{{ pct.toFixed(1) }}%</span>
  </div>
</template>
