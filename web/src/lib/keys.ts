/** True when a key event comes from a text field, so page shortcuts must not fire. */
export function isTyping(target: EventTarget | null): boolean {
  return target instanceof Element && !!target.closest('input, textarea, select, [contenteditable="true"]')
}
