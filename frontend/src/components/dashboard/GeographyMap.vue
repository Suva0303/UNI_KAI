<script setup lang="ts">
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { MapChart } from "echarts/charts";
import { GeoComponent, TooltipComponent, VisualMapContinuousComponent } from "echarts/components";
import { registerMap } from "echarts/core";
import VChart from "vue-echarts";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import type { GeographyRow } from "../../types/dashboard";

use([CanvasRenderer, GeoComponent, MapChart, TooltipComponent, VisualMapContinuousComponent]);

const props = defineProps<{
  rows: GeographyRow[];
  loading: boolean;
  error: string | null;
}>();

const mapReady = ref(false);
const mapLoading = ref(false);
const mapLoadError = ref<string | null>(null);
const nameLookup = ref<Map<string, string>>(new Map());
const selectedMapName = ref<string | null>(null);
const chartRef = ref<InstanceType<typeof VChart> | null>(null);

function mapJsonUrl(): string {
  const base = import.meta.env.BASE_URL || "/";
  const normalized = base.endsWith("/") ? base : `${base}/`;
  return `${normalized}maps/gadm41_RUS_1.json`;
}

function normalizeKey(s: string): string {
  return s
    .normalize("NFD")
    .replace(/\s+/g, "")
    .replace(/[ьъ]/g, "")
    .toLowerCase();
}

type RusGeo = { type: string; features: { properties?: Record<string, string | null> }[]; crs?: unknown };

function buildLookup(geo: RusGeo): Map<string, string> {
  const m = new Map<string, string>();
  for (const f of geo.features) {
    const p = f.properties as Record<string, string | null> | null;
    if (!p) continue;
    const nl = p.NL_NAME_1;
    const en = p.NAME_1;
    const target = (nl && String(nl)) || (en && String(en)) || "";
    if (!target) continue;
    if (nl) m.set(normalizeKey(String(nl)), String(nl));
    if (en) m.set(normalizeKey(String(en)), nl ? String(nl) : String(en));
  }
  return m;
}

function resolveMapName(regionName: string, lookup: Map<string, string>): string | null {
  const n = normalizeKey(regionName);
  if (lookup.has(n)) return lookup.get(n)!;
  for (const [k, v] of lookup) {
    if (n.includes(k) || k.includes(n)) return v;
  }
  return null;
}

function findRowByMapName(mapName: string): GeographyRow | null {
  const lookup = nameLookup.value;
  for (const r of props.rows) {
    const m = resolveMapName(r.region_name, lookup);
    if (m === mapName) return r;
  }
  return null;
}

const seriesData = computed(() => {
  const lookup = nameLookup.value;
  const out: { name: string; value: number; graduates: number; rate: number }[] = [];
  for (const r of props.rows) {
    const name = resolveMapName(r.region_name, lookup);
    if (!name) continue;
    out.push({
      name,
      value: r.employment_rate,
      graduates: r.graduates_count,
      rate: r.employment_rate,
    });
  }
  return out;
});

const valueExtent = computed(() => {
  const vals = props.rows.map((r) => r.employment_rate);
  if (!vals.length) return { min: 0, max: 100 };
  return { min: Math.min(...vals), max: Math.max(...vals) };
});

const chartOption = computed(() => {
  const { min, max } = valueExtent.value;
  const vmin = min === max ? 0 : min;
  const vmax = min === max ? 100 : max;
  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item" as const,
      formatter: (p: { name?: string; data?: { graduates?: number; rate?: number } }) => {
        const name = p.name ?? "";
        const d = p.data as { graduates?: number; rate?: number } | undefined;
        if (d && typeof d.graduates === "number") {
          return `<strong>${name}</strong><br/>Выпускников: ${d.graduates.toLocaleString("ru-RU")}<br/>Трудоустройство: ${d.rate?.toFixed(1) ?? "—"}%<br/><span style="opacity:.85"></span>`;
        }
        return `<strong>${name}</strong><br/>Нет данных по выбранным фильтрам<br/><span style="opacity:.85">Клик — панель под картой</span>`;
      },
    },
    visualMap: {
      show: true,
      left: "left",
      bottom: 24,
      min: vmin,
      max: vmax,
      text: ["Выше, %", "Ниже, %"],
      calculable: true,
      inRange: {
        color: ["#B8D4F0", "#5B8FC7", "#1A4B8C"],
      },
      textStyle: { color: "#2d2d2d", fontSize: 11 },
    },
    series: [
      {
        name: "Трудоустройство",
        type: "map" as const,
        map: "russia",
        roam: true,
        layoutCenter: ["50%", "50%"],
        layoutSize: "92%",
        aspectScale: 0.82,
        nameProperty: "NL_NAME_1",
        emphasis: {
          label: { show: true, color: "#ffffff", fontSize: 11, fontWeight: 600 },
          itemStyle: {
            areaColor: "#0D2F5C",
            borderColor: "#E3F2FD",
            borderWidth: 1,
          },
        },
        itemStyle: {
          areaColor: "#7EB8E8",
          borderColor: "#E8F4FC",
          borderWidth: 0.6,
        },
        data: seriesData.value,
      },
    ],
  };
});

const selectionInfo = computed(() => {
  const name = selectedMapName.value;
  if (!name || !mapReady.value) return null;
  const row = findRowByMapName(name);
  if (row) {
    return {
      title: row.region_name,
      graduates: row.graduates_count,
      rate: row.employment_rate,
      noData: false,
    };
  }
  return {
    title: name,
    graduates: null as number | null,
    rate: null as number | null,
    noData: true,
  };
});

function onMapClick(params: { componentType?: string; seriesType?: string; name?: string }) {
  if (params.componentType !== "series" || params.seriesType !== "map") return;
  const name = params.name;
  if (!name) return;
  selectedMapName.value = name;
}

async function bumpChartSize() {
  await nextTick();
  chartRef.value?.resize();
  requestAnimationFrame(() => chartRef.value?.resize());
  setTimeout(() => chartRef.value?.resize(), 150);
}

watch(mapReady, async (ready) => {
  if (ready) await bumpChartSize();
});

watch(
  () => props.rows,
  () => {
    void bumpChartSize();
  },
  { deep: true },
);

onMounted(async () => {
  mapLoading.value = true;
  mapLoadError.value = null;
  try {
    const url = mapJsonUrl();
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Не удалось загрузить ${url} (HTTP ${res.status})`);
    const geo = (await res.json()) as RusGeo;
    delete geo.crs;
    registerMap("russia", geo as never);
    nameLookup.value = buildLookup(geo);
    mapReady.value = true;
    await bumpChartSize();
  } catch (e) {
    mapLoadError.value =
      e instanceof Error ? e.message : "Ошибка загрузки или разбора GeoJSON карты.";
  } finally {
    mapLoading.value = false;
  }
});
</script>

<template>
  <section class="rounded-2xl border border-charcoal/5 bg-white p-4 shadow-soft">
    <h2 class="mb-3 text-lg font-semibold text-charcoal">География трудоустройства</h2>
    <p v-if="error" class="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <p v-else-if="mapLoadError" class="mb-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      {{ mapLoadError }}
    </p>
    <p v-else-if="mapLoading" class="mb-3 text-sm text-charcoal/70">Загрузка геоданных карты…</p>

    <div class="relative min-h-[420px] w-full min-w-0 overflow-hidden rounded-xl border border-charcoal/10 bg-charcoal/10">
      <div v-if="loading" class="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-white/70">
        <div class="h-10 w-10 animate-spin rounded-full border-2 border-pastel-blue border-t-transparent" />
      </div>
      <div class="h-[420px] w-full min-w-0">
        <VChart
          v-if="mapReady"
          ref="chartRef"
          class="!h-full !w-full min-h-[400px] min-w-0"
          :option="chartOption"
          autoresize
          @click="onMapClick"
        />
        <p v-else-if="!mapLoadError && !mapLoading && !loading" class="py-16 text-center text-sm text-charcoal/60">
          Загрузка карты…
        </p>
      </div>
    </div>

    <div
      v-if="selectionInfo"
      class="mt-4 rounded-xl border border-[#1A4B8C]/25 bg-gradient-to-br from-[#E8F4FC] to-[#B8D4F0]/60 px-4 py-3 shadow-sm"
    >
      <p class="text-xs font-medium uppercase tracking-wide text-[#1A4B8C]/80">Выбранный регион</p>
      <p class="mt-1 text-base font-semibold text-charcoal">{{ selectionInfo.title }}</p>
      <template v-if="!selectionInfo.noData">
        <dl class="mt-2 grid gap-1 text-sm text-charcoal/90 sm:grid-cols-2">
          <div>
            <dt class="text-xs text-charcoal/55">Выпускников</dt>
            <dd class="font-medium tabular-nums">{{ selectionInfo.graduates!.toLocaleString("ru-RU") }}</dd>
          </div>
          <div>
            <dt class="text-xs text-charcoal/55">Трудоустройстроены</dt>
            <dd class="font-medium tabular-nums">{{ selectionInfo.rate!.toFixed(1) }}%</dd>
          </div>
        </dl>
      </template>
      <p v-else class="mt-2 text-sm text-charcoal/70">
        По текущим фильтрам нет строк витрины для этого региона (или название не сопоставилось с данными).
      </p>
    </div>

    <p class="mt-2 text-xs text-charcoal/55">
      Клик по региону показывает выпускников и долю
      трудоустроенных в панели под картой. Интенсивность заливки отражает долю трудоустроенных среди регионов с данными.
    </p>
  </section>
</template>
