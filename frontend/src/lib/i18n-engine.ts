import { UI_DICTIONARY_AR } from "@/lib/i18n-dictionary";

const DYNAMIC_CACHE_STORAGE_KEY = "recova_i18n_dynamic_ar_v1";
const API_BASE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) ||
  "/api/v1";

const LOWER_DICTIONARY_AR: Record<string, string> = {};
for (const [k, v] of Object.entries(UI_DICTIONARY_AR)) {
  const lk = k.toLowerCase();
  if (!(lk in LOWER_DICTIONARY_AR)) {
    LOWER_DICTIONARY_AR[lk] = v;
  }
}

const dynamicCache = new Map<string, string>();
const queuedUnseen = new Set<string>();
const failedUnseen = new Set<string>();
const listeners = new Set<() => void>();

let initialized = false;
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let flushing = false;

const NON_TRANSLATABLE_RE =
  /^(?:[\d\s.,:%+\-–—/()[\]°C]+|MRN[- ]?[A-Za-z0-9-]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|https?:\/\/\S+|[a-fA-F0-9]{16,}|sk-\S+)$/;
const HAS_ARABIC_RE = /[\u0600-\u06FF]/;
const HAS_LATIN_RE = /[A-Za-z]/;

const IGNORED_PAYLOAD_KEYS = new Set([
  "id",
  "user_id",
  "organization_id",
  "patient_id",
  "run_id",
  "referral_id",
  "notice_id",
  "mrn",
  "email",
  "phone",
  "slug",
  "token",
  "password",
  "secret",
  "license_number",
  "sha256",
  "signature_hash",
  "created_at",
  "updated_at",
  "signed_at",
  "detected_at",
  "timestamp",
  "expires_at",
  "read_at",
  "acknowledged_at",
  "summary_en",
  "summary_ar",
  "url",
  "href",
  "code",
]);

function notifyListeners() {
  listeners.forEach((fn) => {
    try {
      fn();
    } catch {
      // Ignore subscriber errors
    }
  });
}

function persistDynamicCache() {
  if (typeof window === "undefined") return;
  try {
    const entries = Array.from(dynamicCache.entries()).slice(-1500);
    window.localStorage.setItem(
      DYNAMIC_CACHE_STORAGE_KEY,
      JSON.stringify(Object.fromEntries(entries))
    );
  } catch {
    // Ignore storage quota issues
  }
}

export function isNonTranslatableToken(raw: string): boolean {
  const norm = raw.trim();
  if (!norm || !HAS_LATIN_RE.test(norm) || HAS_ARABIC_RE.test(norm)) {
    return true;
  }
  return NON_TRANSLATABLE_RE.test(norm);
}

function formatDurationAr(text: string): string {
  return text.replace(/(\d+)\s*([dhm])/g, (_, n: string, unit: string) => {
    const unitAr = unit === "d" ? "ي" : unit === "h" ? "س" : "د";
    return `${n}${unitAr}`;
  });
}

function translatePatternAr(norm: string): string | null {
  let m: RegExpMatchArray | null;

  if ((m = norm.match(/^(\d+)\s+active$/i))) {
    return `${m[1]} نشط`;
  }
  if ((m = norm.match(/^Overdue by (.+)$/i))) {
    return `متأخر بمقدار ${formatDurationAr(m[1])}`;
  }
  if ((m = norm.match(/^(.+) remaining$/i))) {
    return `متبقي ${formatDurationAr(m[1])}`;
  }
  if ((m = norm.match(/^No pages match [“"](.+)[”"]\.?$/i))) {
    return `لا توجد صفحات تطابق "${m[1]}".`;
  }
  if ((m = norm.match(/^ACTIVE EMERGENCY ESCALATION \((\d+)\):/i))) {
    return `تصعيد طوارئ نشط (${m[1]}): مسار الطوارئ (البوابة ٢) مفعّل. يلزم فرز سريري فوري.`;
  }
  if ((m = norm.match(/^(\d+)\s+verified outcomes recorded\./i))) {
    return `تم تسجيل ${m[1]} نتيجة موثّقة. تابع كل إحالة حتى تأكيد النتيجة.`;
  }
  if ((m = norm.match(/^(\d+)\s+overdue follow-ups$/i))) {
    return `${m[1]} متابعات متأخرة`;
  }
  if ((m = norm.match(/^Choose (Recova \w+)$/))) {
    return `اختر ${UI_DICTIONARY_AR[m[1]] ?? m[1]}`;
  }
  if ((m = norm.match(/^Risk Tier:\s*(.+)$/i))) {
    const tier = translateSyncAr(m[1]) ?? m[1];
    return `مستوى الخطر: ${tier}`;
  }
  if ((m = norm.match(/^Consent granted:\s*(.+)$/i))) {
    const scope = translateSyncAr(m[1]) ?? m[1];
    return `تم منح الموافقة: ${scope}`;
  }
  if ((m = norm.match(/^No centers registered for (.+)$/i))) {
    const label = translateSyncAr(m[1]) ?? m[1];
    return `لا توجد مراكز مسجلة لـ ${label}`;
  }
  if ((m = norm.match(/^MRN\s+([A-Za-z0-9-]+)\s+·\s+(.+?)\s+·\s+Registered\s+(.+)$/i))) {
    const pType = translateSyncAr(m[2]) ?? m[2];
    return `ملف ${m[1]} · ${pType} · مسجّل ${m[3]}`;
  }
  if ((m = norm.match(/^(Core|Loop|Neuro|WorkSafe)\s+\((\d+)\)$/i))) {
    const trk = translateSyncAr(m[1]) ?? m[1];
    return `${trk} (${m[2]})`;
  }
  if ((m = norm.match(/^([A-Za-z0-9_ ()/-]+?)\s+enrolled$/i))) {
    const trk = translateSyncAr(m[1]) ?? m[1];
    return `المسجلون في ${trk}`;
  }
  if ((m = norm.match(/^Service Setup — (.+)$/i))) {
    const prog = translateSyncAr(m[1]) ?? m[1];
    return `إعداد الخدمة — ${prog}`;
  }
  if ((m = norm.match(/^Programme Requests \((\d+)\)$/i))) {
    return `طلبات البرامج (${m[1]})`;
  }
  if ((m = norm.match(/^Page\s+(\d+)\s+of\s+(\d+)$/i))) {
    return `صفحة ${m[1]} من ${m[2]}`;
  }

  return null;
}

export function translateSyncAr(raw: string): string | null {
  const norm = raw.trim().replace(/\s+/g, " ");
  if (!norm || isNonTranslatableToken(norm)) {
    return null;
  }

  const exact = UI_DICTIONARY_AR[norm] ?? dynamicCache.get(norm);
  if (exact) return exact;

  const lower = LOWER_DICTIONARY_AR[norm.toLowerCase()];
  if (lower) return lower;

  const pattern = translatePatternAr(norm);
  if (pattern) return pattern;

  if (norm.includes(" · ")) {
    const parts = norm.split(" · ");
    let changed = false;
    const mapped = parts.map((part) => {
      const tr = translateSyncAr(part);
      if (tr) {
        changed = true;
        return tr;
      }
      return part;
    });
    if (changed) return mapped.join(" · ");
  }

  const colonIdx = norm.indexOf(": ");
  if (colonIdx > 1 && colonIdx < 48) {
    const prefix = norm.slice(0, colonIdx);
    const rest = norm.slice(colonIdx + 2);
    const trPrefix = UI_DICTIONARY_AR[prefix] ?? UI_DICTIONARY_AR[`${prefix}:`] ?? LOWER_DICTIONARY_AR[prefix.toLowerCase()];
    if (trPrefix) {
      const cleanPrefix = trPrefix.replace(/:$/, "");
      const trRest = translateSyncAr(rest) ?? rest;
      return `${cleanPrefix}: ${trRest}`;
    }
  }

  return null;
}

async function flushQueuedTranslations() {
  if (flushing || queuedUnseen.size === 0 || typeof fetch === "undefined") {
    return;
  }
  flushing = true;
  const batch = Array.from(queuedUnseen).slice(0, 40);
  batch.forEach((item) => queuedUnseen.delete(item));

  try {
    const res = await fetch(`${API_BASE.replace(/\/+$/, "")}/i18n/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ target_lang: "ar", texts: batch }),
    });
    if (res.ok) {
      const data = (await res.json()) as { translations?: Record<string, string> };
      const map = data?.translations || {};
      let added = 0;
      for (const [src, dst] of Object.entries(map)) {
        if (src && dst && dynamicCache.get(src) !== dst) {
          dynamicCache.set(src, dst);
          added += 1;
        }
      }
      batch.forEach((item) => {
        if (!map[item]) failedUnseen.add(item);
      });
      if (added > 0) {
        persistDynamicCache();
        notifyListeners();
      }
    }
  } catch {
    batch.forEach((item) => failedUnseen.add(item));
  } finally {
    flushing = false;
    if (queuedUnseen.size > 0) {
      scheduleFlush();
    }
  }
}

function scheduleFlush() {
  if (flushTimer || typeof window === "undefined") return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    void flushQueuedTranslations();
  }, 160);
}

export function queueLiveTranslation(raw: string): void {
  if (!initialized) return;
  const norm = raw.trim().replace(/\s+/g, " ");
  if (
    !norm ||
    norm.length < 3 ||
    norm.length > 420 ||
    isNonTranslatableToken(norm) ||
    queuedUnseen.has(norm) ||
    failedUnseen.has(norm) ||
    translateSyncAr(norm) !== null
  ) {
    return;
  }
  queuedUnseen.add(norm);
  scheduleFlush();
}

export function watchIncomingPayload(payload: unknown, depth = 0): void {
  if (typeof window === "undefined" || !payload || depth > 5) return;

  if (typeof payload === "string") {
    queueLiveTranslation(payload);
    return;
  }
  if (Array.isArray(payload)) {
    for (let i = 0; i < Math.min(payload.length, 40); i += 1) {
      watchIncomingPayload(payload[i], depth + 1);
    }
    return;
  }
  if (typeof payload === "object") {
    for (const [key, value] of Object.entries(payload as Record<string, unknown>)) {
      if (IGNORED_PAYLOAD_KEYS.has(key) || key.endsWith("_id") || key.endsWith("_at")) {
        continue;
      }
      if (typeof value === "string") {
        queueLiveTranslation(value);
      } else if (value && typeof value === "object") {
        watchIncomingPayload(value, depth + 1);
      }
    }
  }
}

export function initializeI18nEngine(): void {
  if (typeof window === "undefined" || initialized) return;
  initialized = true;

  try {
    const raw = window.localStorage.getItem(DYNAMIC_CACHE_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Record<string, string>;
      for (const [k, v] of Object.entries(parsed)) {
        if (k && v) dynamicCache.set(k, v);
      }
    }
  } catch {
    // Ignore malformed cache
  }

  const isVitest = typeof process !== "undefined" && Boolean(process.env?.VITEST);
  if (typeof fetch !== "undefined" && !isVitest) {
    void fetch(`${API_BASE.replace(/\/+$/, "")}/i18n/catalog?lang=ar`, {
      credentials: "include",
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { catalog?: Record<string, string> } | null) => {
        if (!data?.catalog) return;
        let updated = 0;
        for (const [k, v] of Object.entries(data.catalog)) {
          if (k && v && !UI_DICTIONARY_AR[k] && dynamicCache.get(k) !== v) {
            dynamicCache.set(k, v);
            updated += 1;
          }
        }
        if (updated > 0) {
          persistDynamicCache();
          notifyListeners();
        }
      })
      .catch(() => undefined);
  }
}

export function subscribeI18nUpdates(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
