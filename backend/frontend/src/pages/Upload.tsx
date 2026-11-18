import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, FileText, Loader2, Check } from "lucide-react";
import { toast } from "sonner";

import { SectionHeader } from "@/components/shared/SectionHeader";
import { Card, CardContent } from "@/components/ui/card";
import { CardTitle } from "@/components/ui/card";
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
    <div className="space-y-8">
      <SectionHeader
        icon={<Upload className="h-4 w-4" />}
        title="Upload textbook"
        description="PDF or DOCX (max 50 MB). Processing starts automatically in the background engine."
      />

      <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: source document */}
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardContent className="p-6">
              <CardTitle className="mb-4 flex items-center gap-2 text-sm font-semibold text-ink">
                <FileText className="h-4 w-4 text-brand" />
                Source document
              </CardTitle>

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
                className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-14 text-center transition-colors ${
                  dragOver
                    ? "border-brand bg-brand-50"
                    : "border-border bg-sand-50 hover:border-brand/40 hover:bg-brand-50/40"
                } cursor-pointer`}
              >
                {file ? (
                  <div className="flex flex-col items-center gap-1.5">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand ring-8 ring-brand/[0.05]">
                      <FileText className="h-7 w-7" />
                    </div>
                    <div className="mt-2 text-sm font-semibold text-foreground">
                      {file.name}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatBytes(file.size)} — click to choose a different file
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sand-100 text-muted-foreground ring-8 ring-sand-200/40">
                      <Upload className="h-7 w-7" />
                    </div>
                    <div className="mt-3 text-sm font-semibold text-foreground">
                      Drop the textbook here, or click to browse
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      PDF or DOCX · up to 50 MB
                    </div>
                  </>
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
            </CardContent>
          </Card>

          {/* Metadata */}
          <Card>
            <CardContent className="grid grid-cols-1 gap-4 p-6 sm:grid-cols-2">
              <div className="space-y-1.5 sm:col-span-2 lg:col-span-1">
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
              <div className="space-y-1.5 sm:col-span-2 lg:col-span-1">
                <Label htmlFor="description">Course description</Label>
                <Input
                  id="description"
                  placeholder="A short description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: publishing profile */}
        <div className="space-y-6">
          <Card>
            <CardContent className="space-y-4 p-6">
              <CardTitle className="text-sm font-semibold text-ink">
                Publishing profile
              </CardTitle>
              <div className="space-y-1.5">
                <Label htmlFor="shortname">Moodle short name</Label>
                <Input
                  id="shortname"
                  placeholder="e.g. ML-AI-101"
                  value={shortname}
                  onChange={(e) => setShortname(e.target.value)}
                />
                <p className="text-[11px] text-muted-foreground">
                  Used at publish time.
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
              <div className="space-y-1.5">
                <Label htmlFor="weeks">Duration</Label>
                <Select value={weeks} onValueChange={setWeeks}>
                  <SelectTrigger id="weeks" className="w-full">
                    <SelectValue placeholder="Choose duration" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="20">20 weeks (5 months)</SelectItem>
                    <SelectItem value="16">16 weeks (4 months)</SelectItem>
                    <SelectItem value="12">12 weeks (3 months)</SelectItem>
                    <SelectItem value="8">8 weeks (2 months)</SelectItem>
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
                    <SelectItem value="6">6</SelectItem>
                    <SelectItem value="7">7</SelectItem>
                    <SelectItem value="4">4</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          <Card className="border-brand/15 bg-brand-50/40">
            <CardContent className="space-y-3 p-6">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold text-ink">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-ai/10 text-ai">
                  <span className="font-mono text-[11px] font-bold">AI</span>
                </span>
                What happens next
              </CardTitle>
              {PIPELINE_HINTS.map((hint) => (
                <div key={hint} className="flex items-start gap-2.5">
                  <span className="mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                    <Check className="h-3 w-3" />
                  </span>
                  <span className="text-xs leading-relaxed text-ink/80">{hint}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Footer */}
        <div className="lg:col-span-3">
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-card">
            <Button type="submit" disabled={uploading} size="lg" className="w-full">
              {uploading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {statusText || "Uploading…"}
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  Upload and begin processing
                </>
              )}
            </Button>
            {uploading && (
              <div className="space-y-1.5">
                <Progress value={progress} />
                <p className="text-right text-xs text-muted-foreground">{statusText}</p>
              </div>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

const PIPELINE_HINTS = [
  "Text is extracted and normalized from the source",
  "AI analysis detects chapters, sections and topics",
  "A 16-week curriculum is planned for your review",
];