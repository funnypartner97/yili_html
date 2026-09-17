import "@testing-library/jest-dom/vitest";

// ProseMirror/Tiptap rely on layout APIs that jsdom does not implement. The
// editor only needs them to not throw during tests, so provide minimal,
// deterministic stubs that return zeroed rectangles.
function createRect(): DOMRect {
  return {
    x: 0,
    y: 0,
    width: 0,
    height: 0,
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    toJSON: () => ({}),
  } as DOMRect;
}

function createRectList(): DOMRectList {
  const rect = createRect();
  const list = [rect] as unknown as DOMRectList;
  Object.defineProperty(list, "length", { value: 1 });
  Object.defineProperty(list, "item", { value: () => rect });
  return list;
}

if (typeof window !== "undefined") {
  const rangeProto = window.Range?.prototype;
  if (rangeProto && !rangeProto.getClientRects) {
    rangeProto.getClientRects = () => createRectList();
  }
  if (rangeProto && !rangeProto.getBoundingClientRect) {
    rangeProto.getBoundingClientRect = () => createRect();
  }

  const elementProto = window.Element?.prototype;
  if (elementProto && !elementProto.getClientRects) {
    elementProto.getClientRects = () => createRectList();
  }
  if (elementProto && !elementProto.scrollIntoView) {
    elementProto.scrollIntoView = () => {};
  }

  // jsdom does not implement layout; ProseMirror queries these on selection.
  if (!window.HTMLElement.prototype.scrollIntoView) {
    window.HTMLElement.prototype.scrollIntoView = () => {};
  }

  // ProseMirror's mousedown handler resolves coordinates to a DOM position via
  // document.elementFromPoint, which jsdom does not provide.
  if (typeof window.document.elementFromPoint !== "function") {
    window.document.elementFromPoint = () => null;
  }
}
