<script setup lang="ts">
import { ChevronDown } from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

export type SelectOption = { value: string | number | null; label: string };

const props = withDefaults(
  defineProps<{
    modelValue: string | number | null;
    options: SelectOption[];
    placeholder?: string;
    borderClass?: string;
    disabled?: boolean;
  }>(),
  {
    placeholder: "Выберите значение",
    borderClass: "border-pastel-lavender",
    disabled: false,
  },
);

const emit = defineEmits<{ "update:modelValue": [string | number | null] }>();

const open = ref(false);
const search = ref("");
const root = ref<HTMLElement | null>(null);

const filteredOptions = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return props.options;
  return props.options.filter((o) => o.label.toLowerCase().includes(q));
});

const displayLabel = computed(() => {
  const hit = props.options.find((o) => o.value === props.modelValue);
  return hit?.label ?? props.placeholder;
});

function pick(v: string | number | null) {
  emit("update:modelValue", v);
  open.value = false;
  search.value = "";
}

function toggle() {
  if (props.disabled) return;
  open.value = !open.value;
}

function onDocClick(e: MouseEvent) {
  const el = root.value;
  if (!el || !open.value) return;
  if (!el.contains(e.target as Node)) {
    open.value = false;
    search.value = "";
  }
}

watch(open, (v) => {
  if (!v) search.value = "";
});

onMounted(() => document.addEventListener("click", onDocClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocClick));
</script>

<template>
  <div ref="root" class="relative min-w-[10rem]">
    <button
      type="button"
      class="flex w-full items-center justify-between gap-1.5 rounded-lg border bg-ivory px-2 py-1 text-left text-xs leading-tight text-charcoal shadow-sm transition hover:bg-ivory-light"
      :class="[borderClass, disabled ? 'cursor-not-allowed opacity-60' : '']"
      :disabled="disabled"
      @click.stop="toggle"
    >
      <span class="truncate">{{ displayLabel }}</span>
      <ChevronDown class="h-3.5 w-3.5 shrink-0 opacity-60" />
    </button>
    <div
      v-if="open"
      class="absolute z-50 mt-0.5 w-full min-w-[12rem] overflow-hidden rounded-lg border border-charcoal/10 bg-white shadow-soft"
      @click.stop
    >
      <input
        v-model="search"
        type="search"
        class="w-full border-b border-charcoal/10 bg-ivory px-2 py-1.5 text-xs outline-none"
        placeholder="Поиск…"
        autocomplete="off"
      />
      <ul class="max-h-44 overflow-auto py-0.5 text-xs">
        <li
          v-for="(opt, idx) in filteredOptions"
          :key="`${idx}-${String(opt.value)}`"
          class="cursor-pointer px-2 py-1.5 hover:bg-pastel-lavender/40"
          :class="opt.value === modelValue ? 'bg-pastel-blue/30 font-medium' : ''"
          @click="pick(opt.value)"
        >
          {{ opt.label }}
        </li>
        <li v-if="filteredOptions.length === 0" class="px-2 py-1.5 text-charcoal/50">Ничего не найдено</li>
      </ul>
    </div>
  </div>
</template>
