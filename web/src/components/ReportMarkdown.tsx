import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/api/client";

interface Props {
  jobId: string;
  target: string;
  markdown: string;
}

export function ReportMarkdown({ jobId, target, markdown }: Props) {
  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex justify-end mb-3">
          <Button asChild variant="outline" size="sm">
            <a href={api.reportUrl(jobId)} download={`${target}_${jobId}.md`}>
              <Download className="h-3.5 w-3.5" /> Download .md
            </a>
          </Button>
        </div>
        <div className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
            {markdown}
          </ReactMarkdown>
        </div>
      </CardContent>
    </Card>
  );
}
