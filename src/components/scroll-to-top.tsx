"use client";

export default function ScrollToTop({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label="Back to top"
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      className="block cursor-pointer"
    >
      {children}
    </button>
  );
}
