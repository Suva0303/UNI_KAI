<script setup lang="ts">
import { computed } from "vue";
import { Bar } from "vue-chartjs";

const props = defineProps<{
  labels: string[];
  data: number[];
  xAxis?: { max: number; ticks: number[] };
}>();

const colors = ["#E6E6FA", "#B2DFDB", "#FFDAB9", "#BBDEFB", "#F8BBD0", "#C8E6C9", "#B3E5FC", "#FADADD"];

const chartData = computed(() => {
  const thin = !!(props.xAxis && props.xAxis.ticks.length);
  return {
    labels: props.labels,
    datasets: [
      {
        data: props.data,
        borderRadius: thin ? 6 : 10,
        maxBarThickness: thin ? 10 : undefined,
        categoryPercentage: thin ? 0.45 : 0.8,
        barPercentage: thin ? 0.75 : 0.9,
        backgroundColor: props.data.map((_, i) => colors[i % colors.length]),
      },
    ],
  };
});

const options = computed(() => {
  const hasCountAxis = !!(props.xAxis && props.xAxis.ticks.length);
  const base: Record<string, unknown> = {
    responsive: true,
    maintainAspectRatio: !hasCountAxis,
    indexAxis: "y" as const,
    plugins: { legend: { display: false } },
  };
  const xa = props.xAxis;
  if (xa && xa.ticks.length) {
    return {
      ...base,
      scales: {
        x: {
          min: 0,
          max: xa.max,
          grid: { color: "rgba(45,45,45,0.06)" },
          afterBuildTicks: (scale: { ticks: { value: number }[] }) => {
            scale.ticks = xa.ticks.map((v) => ({ value: v }));
          },
          ticks: {
            color: "#5a5a5a",
            font: { size: 11 },
            callback: (v: number | string) => String(v),
          },
        },
        y: {
          ticks: { color: "#5a5a5a", font: { size: 11 } },
          grid: { display: false },
        },
      },
    };
  }
  return base;
});
</script>

<template>
  <Bar :data="chartData" :options="options as any" />
</template>
