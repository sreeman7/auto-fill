export function waitForFormSettle(doc: Document, quietMs = 250, maxMs = 1500): Promise<void> {
  return new Promise((resolve) => {
    let finished = false;
    let quietTimer: ReturnType<typeof setTimeout>;
    const maxTimer = setTimeout(done, maxMs);
    const observer = new MutationObserver(() => {
      clearTimeout(quietTimer);
      quietTimer = setTimeout(done, quietMs);
    });
    function done(): void {
      if (finished) return;
      finished = true;
      clearTimeout(quietTimer);
      clearTimeout(maxTimer);
      observer.disconnect();
      resolve();
    }
    observer.observe(doc.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'style', 'hidden', 'disabled', 'required', 'aria-invalid'] });
    quietTimer = setTimeout(done, quietMs);
  });
}
