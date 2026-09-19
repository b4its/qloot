/** Svelte action: fade/slide element in when it enters the viewport. */
export function reveal(node: HTMLElement, options: { delay?: number } = {}) {
  if (typeof IntersectionObserver === "undefined") {
    node.classList.add("in");
    return {};
  }
  node.classList.add("reveal");
  if (options.delay) node.style.transitionDelay = `${options.delay}ms`;

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          node.classList.add("in");
          io.unobserve(node);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" },
  );
  io.observe(node);

  return {
    destroy() {
      io.disconnect();
    },
  };
}
