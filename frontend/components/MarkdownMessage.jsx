import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

const markdownClass =
  "max-w-full break-words text-[14px] leading-6 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_a]:text-[#355db8] [&_a]:underline [&_a]:underline-offset-2 [&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-[#d8d2c4] [&_blockquote]:pl-3 [&_blockquote]:text-[#5d5a52] [&_code]:rounded [&_code]:bg-[#ebe7dc] [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12px] [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-3 [&_pre]:my-3 [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_pre]:rounded-xl [&_pre]:bg-[#262521] [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-[#f5f0e6] [&_table]:my-3 [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto [&_table]:border-collapse [&_td]:border [&_td]:border-[#ded8ca] [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-[#d4ccbc] [&_th]:bg-[#eee9de] [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5";

function linkCitations(text, webSources) {
  const sourceIndexes = new Set(
    (Array.isArray(webSources) ? webSources : [])
      .map((source) => String(source?.index ?? "").trim())
      .filter(Boolean),
  );
  if (sourceIndexes.size === 0) return String(text || "");
  return String(text || "").replace(/\[web:(\d+)\]/g, (match, index) => {
    if (!sourceIndexes.has(index)) return match;
    return `[${match}](#source-web-${index})`;
  });
}

export default function MarkdownMessage({ text = "", webSources = [] }) {
  const markdown = linkCitations(text, webSources);
  return (
    <div className={markdownClass}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          a({ href, children, node, ...props }) {
            void node;
            const citationMatch = String(href || "").match(/^#source-web-(\d+)$/);
            if (citationMatch) {
              return (
                <sup>
                  <a href={href} className="font-semibold no-underline" {...props}>
                    {children}
                  </a>
                </sup>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer noopener" {...props}>
                {children}
              </a>
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
