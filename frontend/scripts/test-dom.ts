/** Give bun test a document so library tests can read what a faculty member would see. */
import { GlobalWindow } from "happy-dom";

const dom = new GlobalWindow({ url: "http://localhost:5173/" });

// React and the tests read these from the global object. Fetch stays Bun's fetch
// so a test can replace it without happy-dom intercepting the API call.
Object.assign(globalThis, {
  window: dom,
  document: dom.document,
  navigator: dom.navigator,
  HTMLElement: dom.HTMLElement,
  Element: dom.Element,
  Node: dom.Node,
  DocumentFragment: dom.DocumentFragment,
  Event: dom.Event,
  MouseEvent: dom.MouseEvent,
  KeyboardEvent: dom.KeyboardEvent,
  // GSAP reads computed styles when the call frame and screen entrances animate.
  getComputedStyle: dom.getComputedStyle.bind(dom),
  IS_REACT_ACT_ENVIRONMENT: true,
});
