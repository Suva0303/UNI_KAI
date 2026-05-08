<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref } from "vue";
import { toast } from "vue-sonner";
import { api } from "../../services/api";

type StudentRow = Record<string, unknown>;

type ImportResultShape = {
  task_id?: string;
  inserted?: number;
  errors?: string[];
  etl?: {
    mart_rows?: number;
  };
};

type ListResponse = {
  items: StudentRow[];
  total: number;
  page: number;
  page_size: number;
};

const STAGING_COLUMNS: { key: string; label: string; required?: boolean }[] = [
  { key: "local_student_id", label: "Локальный ID студента", required: true },
  { key: "university_code", label: "Код вуза", required: true },
  { key: "graduation_year", label: "Год выпуска", required: true },
  { key: "program_code", label: "Код программы" },
  { key: "program_name", label: "Название программы" },
  { key: "specialization_edu_code", label: "Код специализации (обучение)" },
  { key: "specialization_edu_name", label: "Название специализации (обучение)" },
  { key: "birth_year", label: "Год рождения" },
  { key: "gender", label: "Пол" },
  { key: "is_employed", label: "Трудоустроен (да/нет, 0/1)" },
  { key: "company_name", label: "Компания" },
  { key: "inn", label: "ИНН" },
  { key: "industry_name", label: "Отрасль" },
  { key: "position", label: "Должность" },
  { key: "salary", label: "Зарплата" },
  { key: "specialization_work_code", label: "Код специализации (работа)" },
  { key: "specialization_work_name", label: "Название специализации (работа)" },
  { key: "hire_date", label: "Дата найма (ГГГГ-ММ-ДД)" },
  { key: "works_by_specialty", label: "Работа по специальности (да/нет)" },
];

const MART_PAGE_SIZE = 500;

const students = ref<StudentRow[]>([]);
const total = ref(0);
const page = ref(1);
const loadingMart = ref(false);
const importResult = ref<ImportResultShape | null>(null);
const uploading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const selectedFileLabel = ref("");

const manualOpen = ref(false);
const manualSaving = ref(false);
const manualValues = ref<Record<string, string>>({});

const csvUploadHttpError = ref<string | null>(null);
const manualSubmitHttpError = ref<string | null>(null);

const hasMorePages = computed(() => page.value * MART_PAGE_SIZE < total.value);

const HISTORY_PAGE_SIZE = 50;

type BatchDetailShape = {
  task_id?: string;
  aggregate?: Record<string, unknown>;
  audit?: Record<string, unknown> | null;
  errors?: string[];
  logs?: Array<Record<string, unknown> | string>;
  journal_note?: string;
};

const importBatches = ref<Record<string, unknown>[]>([]);
const importBatchesTotal = ref(0);
const importBatchesPage = ref(1);
const importBatchesLoading = ref(false);
const importBatchesPageSize = 50;
const selectedBatchTask = ref("");
const batchDetail = ref<BatchDetailShape | null>(null);
const batchDetailLoading = ref(false);
const stagingHistoryRows = ref<Record<string, unknown>[]>([]);
const stagingHistoryTotal = ref(0);
const stagingHistoryPage = ref(1);
const stagingHistoryLoading = ref(false);

const importBatchesHasMore = computed(() => importBatches.value.length < importBatchesTotal.value);

const historyTableKeys = computed(() => {
  const row = stagingHistoryRows.value[0];
  if (!row) return [...STAGING_COLUMNS.map((c) => c.key), "student_hash", "load_timestamp", "task_id", "id"];
  return Object.keys(row);
});

const rowValidationErrors = computed(() => {
  const e = importResult.value?.errors ?? [];
  return e.filter((line) => /^Строка \d+/.test(line));
});

const otherImportErrors = computed(() => {
  const e = importResult.value?.errors ?? [];
  return e.filter((line) => !/^Строка \d+/.test(line));
});

function resetManualForm() {
  manualValues.value = Object.fromEntries(STAGING_COLUMNS.map((c) => [c.key, ""])) as Record<string, string>;
}

function openManualModal() {
  resetManualForm();
  manualSubmitHttpError.value = null;
  manualOpen.value = true;
}

function closeManualModal() {
  manualOpen.value = false;
}

function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data;
    if (typeof d === "string" && d.trim()) return d.trim();
    if (d && typeof d === "object") {
      const det = (d as { detail?: unknown }).detail;
      if (typeof det === "string" && det.trim()) return det.trim();
      if (Array.isArray(det)) {
        const msg = det
          .map((item) =>
            typeof item === "object" && item !== null && "msg" in item
              ? String((item as { msg: unknown }).msg)
              : JSON.stringify(item),
          )
          .filter(Boolean)
          .join("; ");
        if (msg) return msg;
      }
      if ("message" in d && typeof (d as { message: unknown }).message === "string") {
        return (d as { message: string }).message;
      }
    }
    if (err.response?.status === 413) return "Файл слишком большой для сервера.";
    const st = err.response?.status;
    if (st && st >= 500) return "Ошибка сервера. Проверьте лог бэкенда.";
    return err.message || "Ошибка запроса";
  }
  return "Ошибка загрузки";
}

function formatRuDateTime(v: unknown): string {
  if (v == null || v === "") return "—";
  const d = new Date(String(v));
  if (Number.isNaN(d.getTime())) return String(v);
  return d.toLocaleString("ru-RU");
}

function formatBatchOption(b: Record<string, unknown>): string {
  const tid = String(b.task_id ?? "");
  const last = b.last_load_at ?? b.first_load_at ?? "";
  const n = b.rows_in_staging ?? "0";
  const src = b.audit_source_kind ? ` · ${String(b.audit_source_kind)}` : "";
  const fn = b.audit_filename ? ` · ${String(b.audit_filename)}` : "";
  return `${tid} · ${String(n)} строк${src}${fn} · ${formatRuDateTime(last)}`;
}

function logLineText(log: unknown): string {
  if (typeof log === "string") return log;
  if (log && typeof log === "object" && !Array.isArray(log)) {
    const o = log as Record<string, unknown>;
    const msg = o.msg != null ? String(o.msg) : JSON.stringify(log);
    const at = o.at != null ? String(o.at) : "";
    const lvl = o.level != null ? String(o.level) : "info";
    return `${at} [${lvl}] ${msg}`;
  }
  return JSON.stringify(log);
}

function formatHistoryCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

async function loadImportBatches(p = 1) {
  importBatchesPage.value = p;
  importBatchesLoading.value = true;
  try {
    const { data } = await api.get<{ items: Record<string, unknown>[]; total: number }>("/api/admin/import/batches", {
      params: { page: p, page_size: importBatchesPageSize },
    });
    importBatches.value = data.items ?? [];
    importBatchesTotal.value = data.total ?? 0;
  } catch (e) {
    importBatches.value = [];
    toast.error(formatApiError(e));
  } finally {
    importBatchesLoading.value = false;
  }
}

async function loadMoreImportBatches() {
  if (!importBatchesHasMore.value) return;
  importBatchesLoading.value = true;
  try {
    const next = importBatchesPage.value + 1;
    const { data } = await api.get<{ items: Record<string, unknown>[]; total: number }>("/api/admin/import/batches", {
      params: { page: next, page_size: importBatchesPageSize },
    });
    importBatches.value = [...importBatches.value, ...(data.items ?? [])];
    importBatchesPage.value = next;
    importBatchesTotal.value = data.total ?? importBatchesTotal.value;
  } catch (e) {
    toast.error(formatApiError(e));
  } finally {
    importBatchesLoading.value = false;
  }
}

async function onBatchSelectChange() {
  const tid = selectedBatchTask.value;
  batchDetail.value = null;
  stagingHistoryRows.value = [];
  stagingHistoryTotal.value = 0;
  stagingHistoryPage.value = 1;
  if (!tid) return;
  batchDetailLoading.value = true;
  stagingHistoryLoading.value = true;
  try {
    const [dRes, rRes] = await Promise.all([
      api.get<BatchDetailShape>(`/api/admin/import/batches/${encodeURIComponent(tid)}`),
      api.get<{ items: Record<string, unknown>[]; total: number }>(
        `/api/admin/import/batches/${encodeURIComponent(tid)}/staging-rows`,
        { params: { page: 1, page_size: HISTORY_PAGE_SIZE } },
      ),
    ]);
    batchDetail.value = dRes.data;
    stagingHistoryRows.value = rRes.data.items ?? [];
    stagingHistoryTotal.value = rRes.data.total ?? 0;
  } catch (e) {
    toast.error(formatApiError(e));
  } finally {
    batchDetailLoading.value = false;
    stagingHistoryLoading.value = false;
  }
}

async function loadStagingHistoryPage(p: number) {
  const tid = selectedBatchTask.value;
  if (!tid) return;
  stagingHistoryPage.value = p;
  stagingHistoryLoading.value = true;
  try {
    const { data } = await api.get<{ items: Record<string, unknown>[]; total: number }>(
      `/api/admin/import/batches/${encodeURIComponent(tid)}/staging-rows`,
      { params: { page: p, page_size: HISTORY_PAGE_SIZE } },
    );
    stagingHistoryRows.value = data.items ?? [];
    stagingHistoryTotal.value = data.total ?? 0;
  } catch (e) {
    toast.error(formatApiError(e));
  } finally {
    stagingHistoryLoading.value = false;
  }
}

const stagingHistoryHasMore = computed(() => stagingHistoryPage.value * HISTORY_PAGE_SIZE < stagingHistoryTotal.value);

async function loadMartGraduates(p = 1) {
  page.value = p;
  loadingMart.value = true;
  try {
    const { data } = await api.get<ListResponse>("/api/admin/students", {
      params: { page: page.value, page_size: MART_PAGE_SIZE, sort: "recent" },
    });
    students.value = data.items ?? [];
    total.value = data.total ?? 0;
  } catch (e) {
    students.value = [];
    total.value = 0;
    toast.error(formatApiError(e));
  } finally {
    loadingMart.value = false;
  }
}

function onCsvFileChange(e: Event) {
  const inp = e.target as HTMLInputElement;
  const f = inp.files?.[0];
  selectedFileLabel.value = f ? f.name : "";
}

function summarizeImportToast(data: ImportResultShape, context: string) {
  const ins = data.inserted ?? 0;
  const errs = data.errors ?? [];
  const rowErrLines = errs.filter((line) => /^Строка \d+/.test(line));
  const miscLines = errs.filter((line) => !/^Строка \d+/.test(line));
  const hasRowErr = rowErrLines.length > 0;
  const toastOpts = { duration: 8000 };

  if (ins > 0) {
    const mart = data.etl?.mart_rows;
    toast.success(`${context}: принято ${ins} строк. В mart: ${mart ?? "—"}.`, toastOpts);
    if (miscLines.length) {
      toast.error(miscLines.slice(0, 3).join("; "), toastOpts);
    }
    if (hasRowErr) {
      toast.warning("Часть строк отклонена — см. журнал проверки на странице.", toastOpts);
    }
    return;
  }
  if (hasRowErr && miscLines.length) {
    toast.error(miscLines.slice(0, 3).join("; "), toastOpts);
    toast.warning("Исправьте ошибки в журнале проверки ниже.", toastOpts);
    return;
  }
  if (hasRowErr) {
    toast.warning("Строки не загружены — исправьте ошибки в журнале ниже.", toastOpts);
    return;
  }
  if (miscLines.length) {
    toast.error(miscLines.slice(0, 3).join("; "), toastOpts);
    return;
  }
  toast.info("В файле не было строк данных для загрузки (все строки пустые).", toastOpts);
}

async function uploadCsvFile() {
  const input = fileInput.value;
  const file = input?.files?.[0];
  if (!file) {
    toast.error("Выберите CSV-файл.");
    return;
  }
  uploading.value = true;
  csvUploadHttpError.value = null;
  importResult.value = null;
  const form = new FormData();
  form.append("file", file);
  try {
    const { data } = await api.post<ImportResultShape>("/api/admin/import/csv-file", form);
    importResult.value = data;
    summarizeImportToast(data, "Файл");
    await loadMartGraduates(1);
    await loadImportBatches(1);
    if (data.task_id) {
      selectedBatchTask.value = data.task_id;
      await onBatchSelectChange();
    }
  } catch (e) {
    const msg = formatApiError(e);
    csvUploadHttpError.value = msg;
    toast.error(msg, { duration: 10000 });
  } finally {
    uploading.value = false;
    if (input) input.value = "";
    selectedFileLabel.value = "";
  }
}

async function submitManualRow() {
  manualSaving.value = true;
  manualSubmitHttpError.value = null;
  importResult.value = null;
  try {
    const payload: Record<string, unknown> = {};
    for (const col of STAGING_COLUMNS) {
      const raw = String(manualValues.value[col.key] ?? "").trim();
      if (!col.required && raw === "") continue;
      if (col.key === "birth_year" && raw !== "") {
        const n = Number(raw);
        payload[col.key] = Number.isFinite(n) ? n : raw;
        continue;
      }
      payload[col.key] = raw;
    }

    const { data } = await api.post<ImportResultShape>("/api/admin/import/manual-row", payload);
    importResult.value = data;
    summarizeImportToast(data, "Ручной ввод");
    if ((data.inserted ?? 0) > 0 && (data.errors ?? []).length === 0) {
      closeManualModal();
    }
    await loadMartGraduates(1);
    await loadImportBatches(1);
    if (data.task_id) {
      selectedBatchTask.value = data.task_id;
      await onBatchSelectChange();
    }
  } catch (e) {
    const msg = formatApiError(e);
    manualSubmitHttpError.value = msg;
    toast.error(msg, { duration: 10000 });
  } finally {
    manualSaving.value = false;
  }
}

onMounted(() => {
  resetManualForm();
  void loadMartGraduates(1);
  void loadImportBatches(1);
});
</script>

<template>
  <section class="space-y-8">
    <div>
      <h1 class="text-2xl font-semibold text-charcoal md:text-3xl">Управление выпускниками</h1>
    </div>

    <div class="rounded-2xl border border-matte-lilac/80 bg-white p-5 shadow-sm">
      <h2 class="text-lg font-semibold text-charcoal">Загрузка CSV</h2>
      <div class="mt-4 flex flex-wrap items-end gap-3">
        <div class="flex min-w-0 flex-col gap-1 text-sm">
          <span class="text-charcoal/70">Файл</span>
          <div class="flex flex-wrap items-center gap-2">
            <input
              id="admin-csv-upload"
              ref="fileInput"
              type="file"
              accept=".csv,text/csv"
              class="sr-only"
              @change="onCsvFileChange"
            />
            <label
              for="admin-csv-upload"
              class="inline-flex cursor-pointer rounded-xl border border-matte-lilac/90 bg-[#f1ebfa] px-4 py-2 text-sm font-medium text-[#66508f] hover:bg-[#e8def5]"
            >
              Выберите файл
            </label>
            <span class="truncate text-sm text-charcoal/65" :title="selectedFileLabel || undefined">
              {{ selectedFileLabel || "Файл не выбран" }}
            </span>
          </div>
        </div>
        <button
          type="button"
          class="rounded-xl border border-pastel-mint bg-ivory px-4 py-2 text-sm font-medium hover:bg-pastel-mint/40 disabled:opacity-50"
          :disabled="uploading"
          @click="uploadCsvFile"
        >
          {{ uploading ? "Загрузка…" : "Загрузить данные" }}
        </button>
        <button
          type="button"
          class="rounded-xl border border-matte-lilac/90 bg-ivory px-4 py-2 text-sm font-medium text-charcoal hover:bg-matte-lilac/25"
          :disabled="uploading || manualSaving"
          @click="openManualModal"
        >
          Добавить данные вручную
        </button>
      </div>

      <div
        v-if="uploading"
        class="mt-4 rounded-xl border border-indigo-200 bg-indigo-50/90 px-4 py-3 text-sm text-charcoal"
        role="status"
        aria-live="polite"
      >
        <p class="font-semibold text-charcoal">Идёт загрузка файла и запись в базу…</p>
        <p class="mt-1 text-charcoal/75">
          Пожалуйста, дождитесь ответа сервера. Первый импорт может занять больше времени (создание схемы staging и
          триггеров).
        </p>
      </div>

      <div
        v-else-if="csvUploadHttpError"
        class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-950"
        role="alert"
      >
        <p class="font-semibold">Ошибка при загрузке файла</p>
        <p class="mt-2 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{{ csvUploadHttpError }}</p>
      </div>

      <div v-if="importResult && !uploading" class="mt-4 rounded-xl bg-[#faf8fe] p-4 text-sm text-charcoal/80">
        <p class="font-medium text-charcoal">Результат последнего импорта</p>
        <p class="mt-1 text-xs text-charcoal/60">ID загрузки (task_id): {{ importResult.task_id ?? "—" }}</p>
        <p>
          <span class="font-medium">Сохранено строк в staging:</span>
          {{ importResult.inserted }}
          <span v-if="importResult.etl?.mart_rows != null" class="ml-2">
            · <span class="font-medium">Записей в витрине mart:</span>
            {{ importResult.etl.mart_rows }}
          </span>
        </p>

        <div v-if="rowValidationErrors.length" class="mt-3">
          <p class="text-xs font-semibold uppercase tracking-wide text-charcoal/55">Журнал проверки (только ошибочные строки)</p>
          <ul
            class="mt-2 max-h-52 overflow-auto rounded-lg border border-red-100 bg-white/90 p-3 font-mono text-xs leading-relaxed text-red-900"
          >
            <li v-for="(line, i) in rowValidationErrors" :key="'ve-' + i">{{ line }}</li>
          </ul>
        </div>

        <ul v-if="otherImportErrors.length" class="mt-3 space-y-1 text-sm text-amber-900">
          <li v-for="(line, i) in otherImportErrors" :key="'oe-' + i">{{ line }}</li>
        </ul>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="manualOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        role="dialog"
        aria-modal="true"
      >
        <div class="max-h-[90vh] w-full max-w-3xl overflow-hidden rounded-2xl border border-matte-lilac/80 bg-white shadow-xl">
          <div class="flex items-start justify-between border-b border-matte-lilac/60 px-5 py-4">
            <div>
              <h3 class="text-lg font-semibold text-charcoal">Добавить строку выпускника</h3>
              <p class="mt-1 text-xs text-charcoal/60">
                Поля соответствуют таблице staging и заголовкам CSV. Пустые необязательные поля можно не заполнять.
              </p>
            </div>
            <button
              type="button"
              class="rounded-lg px-2 py-1 text-sm text-charcoal/60 hover:bg-matte-lilac/40"
              :disabled="manualSaving"
              @click="closeManualModal"
            >
              Закрыть
            </button>
          </div>
          <div
            v-if="manualSubmitHttpError"
            class="mx-5 mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-900 whitespace-pre-wrap break-words"
            role="alert"
          >
            {{ manualSubmitHttpError }}
          </div>
          <div class="max-h-[calc(90vh-8rem)] overflow-y-auto px-5 py-4">
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <template v-for="col in STAGING_COLUMNS" :key="col.key">
                <label class="flex flex-col gap-1 text-sm">
                  <span class="text-charcoal/70">
                    {{ col.label }}
                    <span v-if="col.required" class="text-red-600">*</span>
                  </span>
                  <input
                    v-model="manualValues[col.key]"
                    type="text"
                    class="rounded-xl border border-matte-lilac/90 bg-ivory px-3 py-2 text-sm"
                    autocomplete="off"
                  />
                </label>
              </template>
            </div>
          </div>
          <div class="flex justify-end gap-2 border-t border-matte-lilac/60 bg-[#faf8fe] px-5 py-3">
            <button
              type="button"
              class="rounded-xl border border-matte-lilac px-4 py-2 text-sm hover:bg-white"
              :disabled="manualSaving"
              @click="closeManualModal"
            >
              Отмена
            </button>
            <button
              type="button"
              class="rounded-xl border border-pastel-mint bg-ivory px-4 py-2 text-sm font-medium hover:bg-pastel-mint/40 disabled:opacity-50"
              :disabled="manualSaving || !manualValues.local_student_id?.trim() || !manualValues.university_code?.trim() || !manualValues.graduation_year?.trim()"
              @click="submitManualRow"
            >
              {{ manualSaving ? "Сохранение…" : "Сохранить и загрузить" }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <div class="rounded-2xl border border-matte-lilac/80 bg-white p-5 shadow-sm">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 class="text-lg font-semibold text-charcoal">История загрузок</h2>
          <p class="mt-1 max-w-prose text-xs text-charcoal/60">
            Список строится из уникальных task_id: строки в staging плюс записи журнала загрузок в БД (даже если staging уже
            очищен). Ниже можно открыть сохранённые логи ETL и ошибки.
          </p>
          <p
            v-if="!importBatchesLoading && importBatchesTotal === 0 && !loadingMart && total === 0"
            class="mt-2 max-w-prose text-xs text-charcoal/70"
          >
            Если журнал и таблица витрины ниже пустые: выполните загрузку CSV в блоке выше или наполните витрину демоданными
            (переменная окружения бэкенда <code>AUTO_BOOTSTRAP_DASHBOARD=true</code> при старте API либо ручной вызов
            сидирования дашборда из админ-API).
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs text-charcoal/55">Всего: {{ importBatchesTotal }}</span>
          <button
            type="button"
            class="rounded-xl border border-matte-lilac/80 px-3 py-1.5 text-xs disabled:opacity-40"
            :disabled="importBatchesLoading"
            @click="loadImportBatches(1)"
          >
            Обновить
          </button>
          <button
            v-if="importBatchesHasMore"
            type="button"
            class="rounded-xl border border-matte-lilac/80 px-3 py-1.5 text-xs disabled:opacity-40"
            :disabled="importBatchesLoading"
            @click="loadMoreImportBatches"
          >
            Ещё
          </button>
        </div>
      </div>

      <div class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <label class="flex min-w-[min(100%,28rem)] flex-1 flex-col gap-1 text-sm">
          <span class="text-charcoal/70">Выберите загрузку</span>
          <select
            v-model="selectedBatchTask"
            class="rounded-xl border border-matte-lilac/90 bg-ivory px-3 py-2 text-sm"
            @change="onBatchSelectChange"
          >
            <option value="">— не выбрано —</option>
            <option v-for="b in importBatches" :key="String(b.task_id)" :value="String(b.task_id)">
              {{ formatBatchOption(b) }}
            </option>
          </select>
        </label>
      </div>

      <p v-if="importBatchesLoading && !selectedBatchTask" class="mt-3 text-sm text-charcoal/60">Загрузка списка…</p>

      <div v-if="selectedBatchTask" class="mt-5 space-y-5">
        <div v-if="batchDetailLoading" class="text-sm text-charcoal/60">Загрузка деталей…</div>
        <template v-else-if="batchDetail">
          <p v-if="batchDetail.journal_note" class="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-950">
            {{ batchDetail.journal_note }}
          </p>
          <div class="grid gap-4 lg:grid-cols-2">
            <div class="rounded-xl border border-matte-lilac/60 bg-[#faf8fe] p-4 text-sm">
              <p class="font-semibold text-charcoal">Сводка</p>
              <ul class="mt-2 space-y-1 text-xs text-charcoal/80">
                <li>
                  <span class="font-medium">Строк в staging:</span> {{ batchDetail.aggregate?.rows_in_staging ?? "—" }}
                </li>
                <li>
                  <span class="font-medium">Первая запись по времени:</span>
                  {{ formatRuDateTime(batchDetail.aggregate?.first_load_at) }}
                </li>
                <li>
                  <span class="font-medium">Последняя запись по времени:</span>
                  {{ formatRuDateTime(batchDetail.aggregate?.last_load_at) }}
                </li>
                <li v-if="batchDetail.audit?.source_kind">
                  <span class="font-medium">Источник:</span> {{ batchDetail.audit.source_kind }}
                  <span v-if="batchDetail.audit.filename"> · {{ batchDetail.audit.filename }}</span>
                </li>
                <li v-if="batchDetail.audit?.logged_at">
                  <span class="font-medium">Время журнала:</span> {{ formatRuDateTime(batchDetail.audit.logged_at) }}
                </li>
              </ul>
            </div>
            <div class="rounded-xl border border-matte-lilac/60 bg-[#faf8fe] p-4 text-sm">
              <p class="font-semibold text-charcoal">Журнал (логи импорта)</p>
              <ul class="mt-2 max-h-52 overflow-auto font-mono text-xs leading-relaxed text-charcoal/85">
                <li v-for="(lg, li) in batchDetail.logs ?? []" :key="'lg-' + li">{{ logLineText(lg) }}</li>
                <li v-if="!(batchDetail.logs && batchDetail.logs.length)" class="text-charcoal/50">Нет записей.</li>
              </ul>
            </div>
          </div>

          <div v-if="batchDetail.errors?.length" class="rounded-xl border border-red-100 bg-red-50/70 p-4 text-sm">
            <p class="font-semibold text-red-950">Сохранённые ошибки / предупреждения</p>
            <ul class="mt-2 max-h-52 overflow-auto font-mono text-xs text-red-950">
              <li v-for="(er, ei) in batchDetail.errors" :key="'er-' + ei">{{ er }}</li>
            </ul>
          </div>
        </template>

        <div>
          <h3 class="text-sm font-semibold text-charcoal">Данные выпускников этой загрузки (staging)</h3>
          <p v-if="stagingHistoryLoading" class="mt-2 text-xs text-charcoal/60">Загрузка…</p>
          <div v-else class="mt-2 overflow-x-auto">
            <table class="w-full min-w-[800px] text-left text-xs">
              <thead class="text-charcoal/55">
                <tr>
                  <th v-for="k in historyTableKeys" :key="String(k)" class="border-b border-matte-lilac/60 pb-2 pr-2 font-medium">
                    {{ String(k) }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in stagingHistoryRows" :key="ri" class="border-t border-matte-lilac/50">
                  <td
                    v-for="k in historyTableKeys"
                    :key="`${String(k)}-${ri}`"
                    class="max-w-[14rem] truncate py-2 pr-2"
                    :title="formatHistoryCell(row[k])"
                  >
                    {{ formatHistoryCell(row[k]) }}
                  </td>
                </tr>
                <tr v-if="!stagingHistoryRows.length">
                  <td :colspan="Math.max(historyTableKeys.length, 1)" class="py-6 text-center text-charcoal/50">Нет строк.</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="stagingHistoryTotal > 0" class="mt-3 flex flex-wrap justify-between gap-2 text-xs text-charcoal/60">
            <span>Всего {{ stagingHistoryTotal }} строк · страница {{ stagingHistoryPage }}</span>
            <div class="flex gap-2">
              <button
                type="button"
                class="rounded-lg border border-matte-lilac/70 px-2 py-1 disabled:opacity-40"
                :disabled="stagingHistoryPage <= 1 || stagingHistoryLoading"
                @click="loadStagingHistoryPage(stagingHistoryPage - 1)"
              >
                Назад
              </button>
              <button
                type="button"
                class="rounded-lg border border-matte-lilac/70 px-2 py-1 disabled:opacity-40"
                :disabled="!stagingHistoryHasMore || stagingHistoryLoading"
                @click="loadStagingHistoryPage(stagingHistoryPage + 1)"
              >
                Вперёд
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="rounded-2xl border border-matte-lilac/80 bg-white p-5 shadow-sm">
      <h2 class="text-lg font-semibold text-charcoal">Данные о выпускниках</h2>
      <p v-if="loadingMart" class="mt-3 text-sm text-charcoal/60">Загрузка…</p>
      <div class="mt-3 overflow-x-auto">
        <table class="w-full min-w-[900px] text-left text-sm">
          <thead class="text-xs font-medium text-charcoal/55">
            <tr>
              <th class="pb-2 pr-2">Hash</th>
              <th class="pb-2 pr-2">Год</th>
              <th class="pb-2 pr-2">Регион</th>
              <th class="pb-2 pr-2">Вуз</th>
              <th class="pb-2 pr-2">Программа</th>
              <th class="pb-2 pr-2">Трудоустр.</th>
              <th class="pb-2 pr-2">Компания</th>
              <th class="pb-2 pr-2">ЗП</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in students" :key="String(s.student_hash)" class="border-t border-matte-lilac/70">
              <td class="max-w-[120px] truncate py-2 pr-2 font-mono text-xs" :title="String(s.student_hash)">{{ s.student_hash }}</td>
              <td class="py-2 pr-2 tabular-nums">{{ s.graduation_year }}</td>
              <td class="py-2 pr-2">{{ s.region_name }}</td>
              <td class="py-2 pr-2">{{ s.university_name }}</td>
              <td class="py-2 pr-2">{{ s.program_name || s.program_code }}</td>
              <td class="py-2 pr-2">{{ s.is_employed ? "Да" : "Нет" }}</td>
              <td class="py-2 pr-2">{{ s.company_name || "—" }}</td>
              <td class="py-2 pr-2 tabular-nums">{{ s.salary ?? "—" }}</td>
            </tr>
            <tr v-if="!loadingMart && students.length === 0">
              <td colspan="8" class="py-6 text-center text-charcoal/55">Нет записей.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="hasMorePages" class="mt-4 flex justify-end gap-2">
        <button
          type="button"
          class="rounded-xl border border-matte-lilac/80 px-3 py-1.5 text-sm disabled:opacity-40"
          :disabled="page <= 1 || loadingMart"
          @click="loadMartGraduates(page - 1)"
        >
          Назад
        </button>
        <button
          type="button"
          class="rounded-xl border border-matte-lilac/80 px-3 py-1.5 text-sm disabled:opacity-40"
          :disabled="loadingMart"
          @click="loadMartGraduates(page + 1)"
        >
          Далее
        </button>
      </div>
    </div>
  </section>
</template>
