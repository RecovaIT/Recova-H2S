"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import {
  initializeI18nEngine,
  queueLiveTranslation,
  subscribeI18nUpdates,
  translateSyncAr,
} from "@/lib/i18n-engine";

export type AppLanguage = "en" | "ar";

interface LanguageContextValue {
  lang: AppLanguage;
  isAr: boolean;
  setLang: (next: AppLanguage) => void;
  toggleLang: () => void;
  t: (en: string) => string;
  tr: (en: string, ar: string) => string;
}

const STORAGE_KEY = "recova_lang";
const PORTAL_STORAGE_KEY = "recova_portal_lang";

const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "CODE", "PRE", "TEXTAREA", "INPUT"]);
const TRANSLATED_ATTRS = ["placeholder", "title", "aria-label"] as const;

const LanguageContext = createContext<LanguageContextValue>({
  lang: "en",
  isAr: false,
  setLang: () => undefined,
  toggleLang: () => undefined,
  t: (en) => en,
  tr: (en) => en,
});

function applyDocumentDirection(next: AppLanguage) {
  if (typeof document === "undefined") return;
  document.documentElement.lang = next;
  document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  // Always start "en" on SSR + hydration pass so React 19 never drops hydrated nodes;
  // mount effect immediately restores saved preference without hydration mismatch.
  const [lang, setLangState] = useState<AppLanguage>("en");
  const hydratedRef = useRef(false);

  const originalsRef = useRef<WeakMap<Text, string>>(new WeakMap());
  const translatedNodesRef = useRef<Set<Text>>(new Set());
  const attrOriginalsRef = useRef<WeakMap<Element, Partial<Record<string, string>>>>(new WeakMap());
  const attrNodesRef = useRef<Set<Element>>(new Set());
  const originalTitleRef = useRef<string | null>(null);
  const applyingRef = useRef(false);

  const translateDomToArabic = useCallback(() => {
    if (typeof document === "undefined" || !document.body) return;
    applyingRef.current = true;
    try {
      if (document.title) {
        const currentTitle = document.title;
        if (originalTitleRef.current === null) {
          originalTitleRef.current = currentTitle;
        }
        const trTitle = translateSyncAr(originalTitleRef.current);
        if (trTitle && document.title !== trTitle) {
          document.title = trTitle;
        }
      }

      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let current = walker.nextNode();
      while (current) {
        const textNode = current as Text;
        current = walker.nextNode();
        const parent = textNode.parentElement;
        if (!parent || SKIP_TAGS.has(parent.tagName)) continue;
        if (parent.closest("[data-no-translate]")) continue;

        const raw = textNode.nodeValue ?? "";
        if (!raw.trim()) continue;

        const savedOriginal = originalsRef.current.get(textNode);
        const match = raw.match(/^(\s*)([\s\S]*?)(\s*)$/);
        if (!match) continue;
        const [, lead, core, tail] = match;
        const normalized = core.replace(/\s+/g, " ");
        const translated = translateSyncAr(normalized);

        if (translated) {
          if (!savedOriginal || !translatedNodesRef.current.has(textNode)) {
            originalsRef.current.set(textNode, raw);
          } else {
            const origNorm = savedOriginal.trim().replace(/\s+/g, " ");
            if (translateSyncAr(origNorm) !== core) {
              originalsRef.current.set(textNode, raw);
            }
          }
          const nextValue = `${lead}${translated}${tail}`;
          if (textNode.nodeValue !== nextValue) {
            textNode.nodeValue = nextValue;
          }
          translatedNodesRef.current.add(textNode);
        } else if (savedOriginal && translatedNodesRef.current.has(textNode)) {
          const origNorm = savedOriginal.trim().replace(/\s+/g, " ");
          if (translateSyncAr(origNorm) !== normalized) {
            // React replaced this node with new dynamic English copy
            originalsRef.current.delete(textNode);
            translatedNodesRef.current.delete(textNode);
            queueLiveTranslation(normalized);
          }
        } else {
          queueLiveTranslation(normalized);
        }
      }

      const attrSelector = TRANSLATED_ATTRS.map((a) => `[${a}]`).join(",");
      const elements = document.body.querySelectorAll<Element>(attrSelector);
      elements.forEach((el) => {
        if (el.closest("[data-no-translate]")) return;
        let savedMap = attrOriginalsRef.current.get(el);
        for (const attr of TRANSLATED_ATTRS) {
          const val = el.getAttribute(attr);
          if (!val || !val.trim()) continue;
          const trVal = translateSyncAr(val);
          if (trVal) {
            if (!savedMap) {
              savedMap = {};
              attrOriginalsRef.current.set(el, savedMap);
            }
            if (!(attr in savedMap)) {
              savedMap[attr] = val;
            }
            if (val !== trVal) {
              el.setAttribute(attr, trVal);
            }
            attrNodesRef.current.add(el);
          }
        }
      });
    } finally {
      applyingRef.current = false;
    }
  }, []);

  const restoreDomToEnglish = useCallback(() => {
    if (typeof document === "undefined") return;
    applyingRef.current = true;
    try {
      if (originalTitleRef.current !== null && document.title !== originalTitleRef.current) {
        document.title = originalTitleRef.current;
      }

      translatedNodesRef.current.forEach((textNode) => {
        if (!textNode.isConnected) {
          translatedNodesRef.current.delete(textNode);
          return;
        }
        const original = originalsRef.current.get(textNode);
        if (original !== undefined && textNode.nodeValue !== original) {
          textNode.nodeValue = original;
        }
        translatedNodesRef.current.delete(textNode);
      });

      attrNodesRef.current.forEach((el) => {
        if (!el.isConnected) {
          attrNodesRef.current.delete(el);
          return;
        }
        const savedMap = attrOriginalsRef.current.get(el);
        if (savedMap) {
          for (const [attr, original] of Object.entries(savedMap)) {
            if (original !== undefined && el.getAttribute(attr) !== original) {
              el.setAttribute(attr, original);
            }
          }
        }
        attrNodesRef.current.delete(el);
      });
    } finally {
      applyingRef.current = false;
    }
  }, []);

  // Preload catalog & cache immediately on site boot, and restore saved preference post-hydration
  useEffect(() => {
    initializeI18nEngine();
    if (!hydratedRef.current) {
      hydratedRef.current = true;
      try {
        const saved =
          window.localStorage.getItem(STORAGE_KEY) ||
          window.localStorage.getItem(PORTAL_STORAGE_KEY);
        if (saved === "ar") {
          queueMicrotask(() => {
            setLangState("ar");
            applyDocumentDirection("ar");
          });
        }
      } catch {
        // Ignore storage access errors
      }
    }
  }, []);

  // Constant DOM & runtime translation watcher across active sessions and route changes
  useEffect(() => {
    applyDocumentDirection(lang);
    try {
      window.localStorage.setItem(STORAGE_KEY, lang);
      window.localStorage.setItem(PORTAL_STORAGE_KEY, lang);
    } catch {
      // Ignore storage failures in restricted contexts
    }

    if (lang === "ar") {
      translateDomToArabic();
      const unsub = subscribeI18nUpdates(() => {
        translateDomToArabic();
      });

      let observer: MutationObserver | null = null;
      if (typeof MutationObserver !== "undefined" && document.body) {
        observer = new MutationObserver(() => {
          if (!applyingRef.current) {
            translateDomToArabic();
          }
        });
        observer.observe(document.body, {
          childList: true,
          subtree: true,
          characterData: true,
          attributes: true,
          attributeFilter: [...TRANSLATED_ATTRS],
        });
      }

      return () => {
        unsub();
        observer?.disconnect();
      };
    }

    restoreDomToEnglish();
  }, [lang, restoreDomToEnglish, translateDomToArabic]);

  const setLang = useCallback((next: AppLanguage) => {
    setLangState(next);
    applyDocumentDirection(next);
  }, []);

  const toggleLang = useCallback(() => {
    setLangState((prev) => {
      const next: AppLanguage = prev === "en" ? "ar" : "en";
      applyDocumentDirection(next);
      return next;
    });
  }, []);

  const t = useCallback(
    (en: string) => (lang === "ar" ? translateSyncAr(en) ?? en : en),
    [lang]
  );

  const tr = useCallback(
    (en: string, ar: string) => (lang === "ar" ? ar : en),
    [lang]
  );

  return (
    <LanguageContext.Provider value={{ lang, isAr: lang === "ar", setLang, toggleLang, t, tr }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  return useContext(LanguageContext);
}
