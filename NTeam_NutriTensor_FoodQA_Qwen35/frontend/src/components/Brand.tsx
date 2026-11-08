export function Brand({
  compact = false,
  light = false,
}: {
  compact?: boolean;
  light?: boolean;
}) {
  return (
    <span className={`brand ${light ? "brand-light" : ""}`}>
      <svg
        width="31"
        height="36"
        viewBox="0 0 31 36"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M5 27V10L15.5 4L26 10V27L15.5 33L5 27Z"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        <path
          d="M10 23V13L21 23V13M5 10L15.5 16L26 10M15.5 16V33"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
      </svg>
      {!compact && (
        <span>
          <strong>
            nutritensor<span className="brand-period">.</span>
          </strong>
          <small>BY NTEAM</small>
        </span>
      )}
    </span>
  );
}
