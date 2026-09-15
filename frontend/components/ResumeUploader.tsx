"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, FileText, X } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { Resume } from "@/lib/types";

export function ResumeUploader({
  current,
  onUploaded,
}: {
  current: Resume | null;
  onUploaded: (r: Resume) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  async function doUpload(file: File) {
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post<Resume>("/resumes/", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Resume uploaded and parsed");
      onUploaded(data);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) doUpload(f);
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 cursor-pointer transition ${
          dragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-muted-foreground/50"
        }`}
      >
        <Upload className="h-6 w-6 text-muted-foreground" />
        <p className="text-sm font-medium">
          {uploading ? "Uploading…" : "Drop resume here or click to browse"}
        </p>
        <p className="text-xs text-muted-foreground">PDF, DOCX, or TXT · max 5 MB</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) doUpload(f);
            e.target.value = "";
          }}
        />
      </div>

      {current && (
        <div className="flex items-center gap-2 rounded-md border p-3 text-sm">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span className="flex-1 truncate">
            Current resume · uploaded {new Date(current.uploaded_at).toLocaleDateString()}
          </span>
        </div>
      )}
    </div>
  );
}