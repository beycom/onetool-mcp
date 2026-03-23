/**
 * Auto-scroll helper for a chat-style scrolling container.
 *
 * Tracks whether the user is "pinned" to the bottom. When pinned, new items
 * scroll the container to the bottom automatically. Unpins when the user
 * scrolls up, re-pins when they scroll back to within threshold of the bottom.
 */

const SCROLL_THRESHOLD = 80; // px from bottom to count as "pinned"

export function createChatScroller(el: HTMLElement) {
  let pinned = true;

  function isNearBottom(): boolean {
    const { scrollTop, scrollHeight, clientHeight } = el;
    return scrollHeight - scrollTop - clientHeight <= SCROLL_THRESHOLD;
  }

  function scrollToBottom(): void {
    el.scrollTop = el.scrollHeight;
  }

  function onScroll(): void {
    pinned = isNearBottom();
  }

  function onNewContent(): void {
    if (pinned) {
      // Use requestAnimationFrame to wait for the DOM to update
      requestAnimationFrame(() => scrollToBottom());
    }
  }

  el.addEventListener("scroll", onScroll, { passive: true });

  return {
    onNewContent,
    destroy() {
      el.removeEventListener("scroll", onScroll);
    },
  };
}
