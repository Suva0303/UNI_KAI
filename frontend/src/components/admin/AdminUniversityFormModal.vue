<script setup lang="ts">
import axios from "axios";
import { computed, onUnmounted, ref, watch } from "vue";
import { X } from "lucide-vue-next";
import { api } from "../../services/api";
import type { AdminCityOption, AdminUniversityDetail } from "../../types/dashboard";

const props = defineProps<{
  open: boolean;
  mode: "create" | "edit";
  initial: AdminUniversityDetail | null;
  cities: AdminCityOption[];
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
  saved: [];
}>();

const universityCode = ref("");
const universityName = ref("");
const cityIdStr = ref("");
const foundationYear = ref<string>("");
const rating = ref<string>("");
const website = ref("");
const description = ref("");
const logoUrl = ref("");

const citySearch = ref("");
const saving = ref(false);
const errorMsg = ref<string | null>(null);

const codeAutoLinked = ref(true);

function transliterateRuToLatin(input: string): string {
  let s = input.toLowerCase();
  const reps: [RegExp, string][] = [
    [/ё/g, "yo"],
    [/ж/g, "zh"],
    [/х/g, "h"],
    [/ц/g, "ts"],
    [/ч/g, "ch"],
    [/ш/g, "sh"],
    [/щ/g, "sch"],
    [/ъ|ь/g, ""],
    [/ы/g, "y"],
    [/э/g, "e"],
    [/ю/g, "yu"],
    [/я/g, "ya"],
  ];
  for (const [re, v] of reps) s = s.replace(re, v);
  const one: Record<string, string> = {
    а: "a",
    б: "b",
    в: "v",
    г: "g",
    д: "d",
    е: "e",
    з: "z",
    и: "i",
    й: "y",
    к: "k",
    л: "l",
    м: "m",
    н: "n",
    о: "o",
    п: "p",
    р: "r",
    с: "s",
    т: "t",
    у: "u",
    ф: "f",
  };
  let out = "";
  for (const c of s) {
    if (one[c] != null) out += one[c];
    else if (/[a-z0-9]/.test(c)) out += c;
    else out += " ";
  }
  return out;
}

function universityCodeFromName(name: string): string {
  const raw = name.trim();
  if (!raw) return "";
  const latin = transliterateRuToLatin(raw);
  let slug = latin.replace(/[^a-z0-9]/g, "").toUpperCase();
  if (!slug.length) slug = raw.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  return slug.slice(0, 24) || "UNIV";
}

function unlockCodeManual() {
  codeAutoLinked.value = false;
}

function relinkCodeFromName() {
  codeAutoLinked.value = true;
  universityCode.value = universityCodeFromName(universityName.value);
}

const citiesFiltered = computed(() => {
  const q = citySearch.value.trim().toLowerCase();
  if (!q) return props.cities;
  return props.cities.filter(
    (c) =>
      c.city_name.toLowerCase().includes(q) ||
      (c.region_name && c.region_name.toLowerCase().includes(q)),
  );
});

function resetForm() {
  codeAutoLinked.value = true;
  universityCode.value = "";
  universityName.value = "";
  cityIdStr.value = props.cities[0] != null ? String(props.cities[0].city_id) : "";
  foundationYear.value = "";
  rating.value = "";
  website.value = "";
  description.value = "";
  logoUrl.value = "";
  citySearch.value = "";
  errorMsg.value = null;
}

function fillFromInitial(row: AdminUniversityDetail) {
  codeAutoLinked.value = false;
  universityCode.value = row.university_code ?? "";
  universityName.value = row.university_name ?? "";
  cityIdStr.value = row.city_id != null ? String(row.city_id) : "";
  foundationYear.value = row.foundation_year != null ? String(row.foundation_year) : "";
  rating.value = row.rating != null ? String(row.rating) : "";
  website.value = row.website ?? "";
  description.value = row.description ?? "";
  logoUrl.value = row.logo_url ?? "";
  citySearch.value = "";
  errorMsg.value = null;
}

watch(
  () => [props.open, props.initial, props.mode] as const,
  () => {
    if (!props.open) return;
    if (props.mode === "edit" && props.initial) fillFromInitial(props.initial);
    else resetForm();
  },
  { flush: "post" },
);

watch(universityName, (name) => {
  if (!props.open || props.mode !== "create" || !codeAutoLinked.value) return;
  universityCode.value = universityCodeFromName(name);
});

watch(
  () => props.open,
  (v) => {
    if (typeof document === "undefined") return;
    document.body.style.overflow = v ? "hidden" : "";
  },
  { immediate: true },
);

onUnmounted(() => {
  if (typeof document !== "undefined") document.body.style.overflow = "";
});

function close() {
  emit("update:open", false);
}

function normalizeWebsite(s: string): string | null {
  const t = s.trim();
  if (!t) return null;
  if (/^https?:\/\//i.test(t)) return t;
  return `https://${t}`;
}

function parseIntOrNull(s: string): number | null {
  const n = parseInt(s, 10);
  return Number.isFinite(n) ? n : null;
}

function parseFloatOrNull(s: string): number | null {
  if (!s.trim()) return null;
  const n = parseFloat(s.replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

async function submit() {
  errorMsg.value = null;
  if (!universityCode.value.trim() || !universityName.value.trim()) {
    errorMsg.value = "Укажите код и полное название вуза.";
    return;
  }
  const cityIdNum = parseInt(cityIdStr.value, 10);
  if (!Number.isFinite(cityIdNum)) {
    errorMsg.value = "Выберите город.";
    return;
  }
  saving.value = true;
  try {
    const payload = {
      university_code: universityCode.value.trim(),
      university_name: universityName.value.trim(),
      city_id: cityIdNum,
      foundation_year: parseIntOrNull(foundationYear.value),
      rating: parseFloatOrNull(rating.value),
      website: normalizeWebsite(website.value),
      description: description.value.trim() || null,
      logo_url: logoUrl.value.trim() || null,
    };
    if (props.mode === "create") {
      await api.post("/api/admin/universities", payload);
    } else if (props.initial) {
      await api.put(`/api/admin/universities/${props.initial.university_id}`, payload);
    }
    emit("saved");
    emit("update:open", false);
  } catch (e) {
    if (axios.isAxiosError(e)) {
      const d = e.response?.data as { detail?: unknown } | undefined;
      const det = d?.detail;
      errorMsg.value =
        typeof det === "string" ? det : e.response?.status === 422 ? "Проверьте формат полей." : e.message;
    } else {
      errorMsg.value = "Не удалось сохранить.";
    }
  } finally {
    saving.value = false;
  }
}

const title = computed(() => (props.mode === "create" ? "Новый вуз" : "Редактирование вуза"));

function onLogoError(e: Event) {
  const el = e.target as HTMLImageElement | null;
  if (el) el.style.display = "none";
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[80] flex items-end justify-center p-4 sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="'uni-modal-title'"
    >
      <div
        class="absolute inset-0 bg-charcoal/45 backdrop-blur-[3px]"
        aria-hidden="true"
        @click="close"
      />
      <div
        class="relative flex max-h-[min(92vh,44rem)] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-matte-lilac/95 bg-[#f3f0f8] shadow-soft"
      >
        <header
          class="flex shrink-0 items-start justify-between gap-3 border-b border-matte-lilac/80 bg-matte-dust/50 px-5 py-4"
        >
          <div>
            <h2 id="uni-modal-title" class="text-lg font-semibold text-charcoal">{{ title }}</h2>
            <p class="mt-0.5 text-xs text-charcoal/55">Поля соответствуют таблице dwh.dim_university</p>
          </div>
          <button
            type="button"
            class="rounded-xl p-2 text-charcoal/50 transition hover:bg-matte-lilac/60 hover:text-charcoal"
            aria-label="Закрыть"
            @click="close"
          >
            <X class="h-5 w-5" stroke-width="2" />
          </button>
        </header>

        <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <p v-if="errorMsg" class="mb-3 rounded-xl border border-red-200/80 bg-red-50/90 px-3 py-2 text-sm text-red-800">
            {{ errorMsg }}
          </p>

          <div class="grid gap-3 sm:grid-cols-2">
            <label class="flex flex-col gap-1 sm:col-span-2">
              <span class="text-xs font-medium text-charcoal/65">Полное название <span class="text-red-600">*</span></span>
              <input
                v-model="universityName"
                type="text"
                class="rounded-xl border border-matte-lilac/90 bg-white/90 px-3 py-2.5 text-sm text-charcoal shadow-sm outline-none focus:ring-2 focus:ring-pastel-lavender/40"
                placeholder="Наименование как в справочнике"
              />
            </label>
            <div class="flex flex-col gap-1 sm:col-span-1">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="text-xs font-medium text-charcoal/65">Код вуза <span class="text-red-600">*</span></span>
                <template v-if="mode === 'create'">
                  <button
                    v-if="codeAutoLinked"
                    type="button"
                    class="text-[11px] font-medium text-charcoal/55 underline decoration-charcoal/25 underline-offset-2 hover:text-charcoal"
                    @click="unlockCodeManual"
                  >
                    Задать вручную
                  </button>
                  <button
                    v-else
                    type="button"
                    class="text-[11px] font-medium text-charcoal/55 underline decoration-charcoal/25 underline-offset-2 hover:text-charcoal"
                    @click="relinkCodeFromName"
                  >
                    Из названия
                  </button>
                </template>
              </div>
              <input
                v-model="universityCode"
                type="text"
                autocomplete="off"
                :readonly="mode === 'create' && codeAutoLinked"
                class="rounded-xl border border-matte-lilac/90 bg-white/90 px-3 py-2.5 text-sm text-charcoal shadow-sm outline-none ring-pastel-lavender/40 placeholder:text-charcoal/35 focus:ring-2 read-only:bg-matte-dust/40 read-only:text-charcoal/80"
                :placeholder="mode === 'create' && codeAutoLinked ? 'Подставится из названия' : 'Например MIREA'"
              />
              <p v-if="mode === 'create' && codeAutoLinked" class="text-[11px] text-charcoal/45">
                Латинские буквы и цифры, до 24 символов. Можно переключить на ручной ввод.
              </p>
            </div>
            <label class="flex flex-col gap-1 sm:col-span-1">
              <span class="text-xs font-medium text-charcoal/65">Год основания</span>
              <input
                v-model="foundationYear"
                type="number"
                inputmode="numeric"
                class="rounded-xl border border-matte-lilac/90 bg-white/90 px-3 py-2.5 text-sm text-charcoal shadow-sm outline-none focus:ring-2 focus:ring-pastel-lavender/40"
                placeholder="1947"
              />
            </label>
            <label class="flex flex-col gap-1 sm:col-span-2">
              <span class="text-xs font-medium text-charcoal/65">Город <span class="text-red-600">*</span></span>
              <input
                v-model="citySearch"
                type="search"
                class="mb-1 rounded-xl border border-matte-lilac/90 bg-white/90 px-3 py-2 text-sm text-charcoal shadow-sm outline-none focus:ring-2 focus:ring-pastel-lavender/40"
                placeholder="Поиск города или региона…"
              />
              <select
                v-model="cityIdStr"
                class="rounded-xl border border-matte-lilac/90 bg-white/90 px-3 py-2.5 text-sm text-charcoal shadow-sm outline-none focus:ring-2 focus:ring-pastel-lavender/40"
              >
                <option value="" disabled>Выберите город</option>
                <option v-for="c in citiesFiltered" :key="c.city_id" :value="String(c.city_id)">
                  {{ c.city_name }}{{ c.region_name ? ` — ${c.region_name}` : "" }}
                </option>
              </select>
            </label>
            <label class="flex flex-col gap-1">
              <span class="text-xs font-medium text-charcoal/65">Рейтинг</span>
              <input
                v-model="rating"
                type="text"
                inputmode="decimal"
                class="rounded-xl border border-matte-lilac/90 bg-white/90 px-3 py-2.5 text-sm text-charcoal shadow-sm outline-none focus:ring-2 focus:ring-pastel-lavender/40"
                placeholder="4.5"
              />
            </label>
            <label class="flex flex-col gap-1">
              <span class="text-xs font-medium text-charcoal/65">Сайт</span>
              <input
                v-model="website"
                type="url"
                class="rounded-xl border border-matte-lilac/90 bg-white/90 px-3 py-2.5 text-sm text-charcoal shadow-sm outline-none focus:ring-2 focus:ring-pastel-lavender/40"
                placeholder="https://…"
              />
            </label>
            <label class="flex flex-col gap-1 sm:col-span-2">
              <span class="text-xs font-medium text-charcoal/65">URL логотипа</span>
              <input
                v-model="logoUrl"
                type="url"
                class="rounded-xl border border-matte-lilac/90 bg-white/90 px-3 py-2.5 text-sm text-charcoal shadow-sm outline-none focus:ring-2 focus:ring-pastel-lavender/40"
                placeholder="https://…"
              />
            </label>
            <div v-if="logoUrl.trim()" class="sm:col-span-2">
              <p class="mb-1 text-xs font-medium text-charcoal/55">Предпросмотр</p>
              <div
                class="flex h-24 w-24 items-center justify-center overflow-hidden rounded-xl border border-matte-lilac/80 bg-white/80"
              >
                <img :src="logoUrl.trim()" alt="" class="max-h-full max-w-full object-contain" @error="onLogoError" />
              </div>
            </div>
            <label class="flex flex-col gap-1 sm:col-span-2">
              <span class="text-xs font-medium text-charcoal/65">Описание</span>
              <textarea
                v-model="description"
                rows="4"
                class="resize-y rounded-xl border border-matte-lilac/90 bg-white/90 px-3 py-2.5 text-sm text-charcoal shadow-sm outline-none focus:ring-2 focus:ring-pastel-lavender/40"
                placeholder="Краткое описание для карточки…"
              />
            </label>
          </div>
        </div>

        <footer
          class="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-matte-lilac/80 bg-matte-dust/40 px-5 py-4"
        >
          <button
            type="button"
            class="rounded-xl border border-matte-lilac/90 bg-white/80 px-4 py-2.5 text-sm font-medium text-charcoal/80 shadow-sm transition hover:border-pastel-lavender hover:bg-white"
            @click="close"
          >
            Отмена
          </button>
          <button
            type="button"
            class="rounded-xl border border-matte-sage/80 bg-matte-sage/35 px-4 py-2.5 text-sm font-semibold text-charcoal shadow-sm transition hover:bg-matte-sage/55 disabled:opacity-50"
            :disabled="saving"
            @click="submit"
          >
            {{ saving ? "Сохранение…" : mode === "create" ? "Создать" : "Сохранить" }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
