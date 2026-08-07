import { useEffect } from "react";

// Closes a popup when the user clicks anywhere outside it (or presses Escape).
// Pass every element that counts as "inside" — typically the popup itself AND its
// trigger button, so clicking the trigger still reaches its own toggle handler
// instead of being treated as an outside click.
export default function useClickOutside(refs, active, onClose) {
  useEffect(() => {
    if (!active) return undefined;
    const refList = Array.isArray(refs) ? refs : [refs];
    const handleMouseDown = (event) => {
      const inside = refList.some((ref) => ref?.current && ref.current.contains(event.target));
      if (!inside) onClose();
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [refs, active, onClose]);
}
