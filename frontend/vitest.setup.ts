import "@testing-library/jest-dom/vitest";

// jsdom has no canvas. The ambient background already copes with a missing
// 2D context; this keeps jsdom from logging "not implemented" for every render.
HTMLCanvasElement.prototype.getContext = (() => null) as unknown as HTMLCanvasElement["getContext"];

// Tests read final values, so they run as if the device asked for reduced motion:
// numbers render at once instead of counting up.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  window.matchMedia = ((query: string) => ({
    matches: query.includes("prefers-reduced-motion"),
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}
