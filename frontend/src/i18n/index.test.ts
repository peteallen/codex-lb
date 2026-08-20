import { describe, expect, it } from "vitest";

import i18n, { normalizeSupportedLanguage, SUPPORTED_LANGUAGES } from "@/i18n";

describe("normalizeSupportedLanguage", () => {
  it("keeps exact supported locales", () => {
    expect(normalizeSupportedLanguage("en")).toBe("en");
    expect(normalizeSupportedLanguage("zh-CN")).toBe("zh-CN");
  });

  it("normalizes detected regional locales to supported toggle values", () => {
    expect(normalizeSupportedLanguage("en-US")).toBe("en");
    expect(normalizeSupportedLanguage("zh")).toBe("zh-CN");
    expect(normalizeSupportedLanguage("zh-Hans-CN")).toBe("zh-CN");
    expect(normalizeSupportedLanguage("ZH-cn")).toBe("zh-CN");
  });

  it("falls back to English for missing or unsupported locales", () => {
    expect(normalizeSupportedLanguage(undefined)).toBe("en");
    expect(normalizeSupportedLanguage("fr-FR")).toBe("en");
  });

  it("keeps normalized Chinese detections on the supported zh-CN resource", async () => {
    await i18n.changeLanguage(normalizeSupportedLanguage("zh"));

    expect(i18n.resolvedLanguage).toBe("zh-CN");
  });

  it.each(SUPPORTED_LANGUAGES)("includes v1.23 dashboard copy in %s", (language) => {
    const keys = [
      "dashboard.filters.customRange",
      "dashboard.filters.customRangeAria",
      "dashboard.filters.customRangeStart",
      "dashboard.filters.customRangeStartAria",
      "dashboard.filters.customRangeEnd",
      "dashboard.filters.customRangeEndAria",
      "dashboard.requests.firstOutputApproxHint",
    ];

    for (const key of keys) {
      expect(i18n.exists(key, { lng: language })).toBe(true);
      expect(i18n.t(key, { lng: language, start: "2026-06-01", end: "2026-06-07" })).not.toBe(key);
    }
  });
});
