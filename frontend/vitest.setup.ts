import "@testing-library/jest-dom/vitest";

// jsdom has no canvas. The ambient background already copes with a missing
// 2D context; this keeps jsdom from logging "not implemented" for every render.
HTMLCanvasElement.prototype.getContext = (() => null) as unknown as HTMLCanvasElement["getContext"];
