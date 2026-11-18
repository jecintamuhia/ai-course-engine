import DOMPurify from "dompurify";

/**
 * Render published lesson HTML safely.
 *
 * Lesson content originates in Moodle Page activities, which Moodle
 * administrators can edit independently of this application. Treating
 * that HTML as trusted would allow stored XSS in the learner and
 * lecturer portals, so it is sanitised before insertion. Script-capable
 * elements are forbidden outright; DOMPurify also strips event-handler
 * attributes and javascript: URLs by default.
 */
export function SafeHtml({
  html,
  className,
}: {
  html: string;
  className?: string;
}) {
  const clean = DOMPurify.sanitize(html, {
    FORBID_TAGS: ["script", "iframe", "object", "embed", "form", "base"],
    FORBID_ATTR: ["srcdoc", "formaction"],
  });

  return (
    <div
      className={className}
      // Sanitised above; see the security note on this component.
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
}
