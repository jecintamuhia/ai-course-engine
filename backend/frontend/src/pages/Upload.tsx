import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, File, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { saveDraft } from "@/lib/drafts";

export function UploadPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("");

  // Form fields
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [shortname, setShortname] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [weeks, setWeeks] = useState("16");
  const [days, setDays] = useState("5");

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      toast.error("Please choose a textbook file first.");
      return;
    }

    setUploading(true);
    setProgress(0);
    setStatusText("Uploading…");

    try {
      const result = await api.uploadDocument(file, (pct) => {
        setProgress(pct);
        setStatusText(`Uploading… ${pct}%`);
      });

      const docId = result.document.id;
      setProgress(100);
      setStatusText(
        result.is_duplicate
          ? "Duplicate content detected — reusing existing document."
          : "Upload complete.",
      );

      saveDraft(docId, {
        title: title.trim() || null,
        description: description.trim() || null,
        shortname: shortname.trim() || null,
        category_id: Number(categoryId) || null,
        total_weeks: Number(weeks),
        learning_days_per_week: Number(days),
      });

      toast.success("Document uploaded. Opening the processing screen…");
      navigate(`/document/${docId}`);
    } catch (err) {
      setStatusText("");
      toast.error((err as Error).message);
      setUploading(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Upload textbook"
        description="PDF or DOCX (max 50 MB). Processing starts automatically through the background worker."
      />

      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Drop zone */}
            <div className="space-y-1.5">
              <Label>
                Source document <span className="text-red-500">*</span>
              </Label>
              <div
                role="button"
                tabIndex={0}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
                  dragOver
                    ? "border-burgundy bg-burgundy-50"
                    : "border-border bg-cream-50 hover:border-burgundy/40 hover:bg-burgundy-50/40"
                } cursor-pointer`}
              >
                {file ? (
                  <div className="flex flex-col items-center gap-1.5">
                    <File className="h-8 w-8 text-burgundy-600" />
                    <div className="text-sm font-semibold text-foreground">{file.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {formatBytes(file.size)} — click to change
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-1.5">
                    <Upload className="h-8 w-8 text-muted-foreground" />
                    <div className="text-sm font-semibold text-foreground">
                      Drop your textbook here, or click to browse
                    </div>
                    <div className="text-xs text-muted-foreground">PDF or DOCX</div>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files?.[0]) setFile(e.target.files[0]);
                  }}
                />
              </div>
            </div>

            {/* Metadata */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="title">Course name</Label>
                <Input
                  id="title"
                  placeholder="e.g. Machine Learning"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
                <p className="text-[11px] text-muted-foreground">
                  Defaults to the file name when generating the curriculum.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="description">Course description</Label>
                <Input
                  id="description"
                  placeholder="A short description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="shortname">Moodle short name</Label>
                <Input
                  id="shortname"
                  placeholder="e.g. ML-AI-101"
                  value={shortname}
                  onChange={(e) => setShortname(e.target.value)}
                />
                <p className="text-[11px] text-muted-foreground">
                  Used as the Moodle course short name at publish time.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="category">Moodle category id</Label>
                <Input
                  id="category"
                  type="number"
                  min="1"
                  placeholder="1"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                />
                <p className="text-[11px] text-muted-foreground">
                  Defaults to the configured MOODLE_COURSE_CATEGORY_ID.
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="weeks">Duration (weeks)</Label>
                <Select value={weeks} onValueChange={setWeeks}>
                  <SelectTrigger id="weeks" className="w-full">
                    <SelectValue placeholder="Choose duration" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="16">16 weeks (4 months)</SelectItem>
                    <SelectItem value="12">12 weeks (3 months)</SelectItem>
                    <SelectItem value="8">8 weeks (2 months)</SelectItem>
                    <SelectItem value="20">20 weeks (5 months)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="days">Learning days per week</Label>
                <Select value={days} onValueChange={setDays}>
                  <SelectTrigger id="days" className="w-full">
                    <SelectValue placeholder="Choose days" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="5">5</SelectItem>
                    <SelectItem value="4">4</SelectItem>
                    <SelectItem value="6">6</SelectItem>
                    <SelectItem value="7">7</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Upload button & progress */}
            <div className="space-y-3">
              <Button type="submit" disabled={uploading}>
                {uploading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Uploading…
                  </>
                ) : (
                  "Upload and begin processing"
                )}
              </Button>
              {uploading && (
                <div className="space-y-1.5">
                  <Progress value={progress} />
                  <p className="text-xs text-muted-foreground">{statusText}</p>
                </div>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  );
}