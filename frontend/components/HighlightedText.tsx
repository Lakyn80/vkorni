"use client";

import { HIGHLIGHT_WORDS, buildHighlightRegex } from "@/utils/text";

type Props = { text: string };

export function HighlightedText({ text }: Props) {
  if (!text) return null;
  const regex = buildHighlightRegex();
  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, index) => {
        const lower = part.toLowerCase();
        const isYear = /^\d{4}$/.test(part);
        const isKeyword = HIGHLIGHT_WORDS.includes(lower);
        if (isYear || isKeyword) {
          return <span key={`${part}-${index}`} className="memorial-mark">{part}</span>;
        }
        return <span key={`${part}-${index}`}>{part}</span>;
      })}
    </>
  );
}
