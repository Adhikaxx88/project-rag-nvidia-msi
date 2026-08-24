export function Skeleton() {
  return (
    <div className="skeleton" aria-label="Loading answer">
      <div className="skeleton-line" style={{ width: "92%" }} />
      <div className="skeleton-line" style={{ width: "78%" }} />
      <div className="skeleton-line" style={{ width: "85%" }} />
    </div>
  );
}
