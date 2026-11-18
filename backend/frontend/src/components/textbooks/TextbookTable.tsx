import { Link } from "react-router-dom";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ingestBadge } from "@/lib/badges";
import { formatDate } from "@/lib/format";
import type { DocumentOverview } from "@/lib/types";

interface TextbookTableProps {
  documents: DocumentOverview[];
}

export function TextbookTable({ documents }: TextbookTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Document</TableHead>
          <TableHead>Progress</TableHead>
          <TableHead className="text-right">Pages</TableHead>
          <TableHead className="text-right">Chunks</TableHead>
          <TableHead className="text-right">Topics</TableHead>
          <TableHead className="text-right">Curricula</TableHead>
          <TableHead className="text-right">Uploaded</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {documents.map((d) => {
          const badge = ingestBadge(d.latest_job?.status ?? null);
          return (
            <TableRow key={d.document.id}>
              <TableCell>
                <Link
                  to={`/document/${d.document.id}`}
                  className="font-medium text-brand-700 hover:text-brand-800 hover:underline"
                >
                  {d.document.original_filename}
                </Link>
              </TableCell>
              <TableCell>
                <StatusBadge tone={badge.tone} label={badge.label} />
              </TableCell>
              <TableCell className="text-right tabular-nums">{d.page_count}</TableCell>
              <TableCell className="text-right tabular-nums">{d.chunk_count}</TableCell>
              <TableCell className="text-right tabular-nums">{d.topic_count}</TableCell>
              <TableCell className="text-right tabular-nums">{d.curriculum_count}</TableCell>
              <TableCell className="text-right text-muted-foreground">
                {formatDate(d.document.created_at)}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}