"use client";

import { useEffect } from "react";

import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

interface Props {
  text: string;
  label: string;
  editable?: boolean;
  onChangeText?: (text: string) => void;
}

/** Editable rich-text block backed by Tiptap; the contract stores plain text. */
export default function RichTextBlock({ text, label, editable = true, onChangeText }: Props) {
  const editor = useEditor({
    extensions: [StarterKit],
    content: text,
    editable,
    immediatelyRender: false,
    editorProps: { attributes: { "aria-label": label, role: "textbox" } },
    onUpdate: ({ editor: instance }) => {
      onChangeText?.(instance.getText({ blockSeparator: "\n" }));
    },
  });

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    if (editor.getText({ blockSeparator: "\n" }) !== text) {
      editor.commands.setContent(text, { emitUpdate: false });
    }
  }, [editor, text]);

  return <div className="rich-text-block"><EditorContent editor={editor} /></div>;
}
