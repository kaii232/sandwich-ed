"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import QuizComponent from "./QuizComponent";

export type Lesson = {
  id: string;
  title: string;
  summary: string;
  expandable: boolean;
  loaded?: boolean;
  lesson_info: Record<string, any>;
  content?: string;
  videos?: {
    title?: string | null;
    channel?: string | null;
    url: string;
    description?: string | null;
    thumbnail?: string | null;
    published?: string | null;
    is_search?: boolean;
  }[];
};

// Lesson component for individual lesson content
function LessonComponent({ 
  lesson, 
  onLoadLesson,
  weekInfo,
  onNavigateNext
}: { 
  lesson: any; 
  onLoadLesson?: (info: any) => Promise<any | null>; 
  weekInfo?: any;
  onNavigateNext?: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<any>(null);

  // Auto-load content when component mounts or lesson changes
  useEffect(() => {
    if (onLoadLesson && !loading) {
      // Reset content when lesson changes and load new content
      setContent(null);
      loadContent();
    }
  }, [lesson.id]);

  const loadContent = async () => {
    if (!onLoadLesson || loading) return;
    
    setLoading(true);
    try {
      const loadedContent = await onLoadLesson(lesson.lesson_info);
      setContent(loadedContent);
    } catch (error) {
      console.error("Error loading lesson content:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-4 w-1/2 bg-neutral-200 rounded" />
        <div className="h-3 w-2/3 bg-neutral-200 rounded" />
        <div className="h-3 w-2/5 bg-neutral-200 rounded" />
        <div className="h-48 w-full bg-neutral-200 rounded-xl" />
      </div>
    );
  }

  if (!content) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-4 w-1/2 bg-neutral-200 rounded" />
        <div className="h-3 w-2/3 bg-neutral-200 rounded" />
        <div className="h-3 w-2/5 bg-neutral-200 rounded" />
        <div className="h-48 w-full bg-neutral-200 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="prose prose-neutral max-w-none">
        <div dangerouslySetInnerHTML={{ __html: mdToHtml(content.content || "") }} />
        {content.videos && content.videos.length > 0 && (
          <div className="not-prose mt-6">
            <h4 className="text-lg font-semibold mb-3">Related Videos</h4>
            <div className="grid sm:grid-cols-2 gap-3">
              {content.videos.map((video: any, index: number) => (
                <a
                  key={index}
                  href={video.url}
                  target="_blank"
                  className="block rounded-lg border p-3 hover:bg-neutral-50 transition"
                >
                  <div className="font-medium text-sm">{video.title}</div>
                  <div className="text-xs text-neutral-600 mt-1">{video.channel}</div>
                  {video.description && (
                    <div className="text-xs text-neutral-500 mt-2 line-clamp-2">
                      {video.description}
                    </div>
                  )}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
      
      {/* Lesson Navigation */}
      <div className="pt-6 border-t">
        <div className="flex items-center justify-between">
          <div className="text-sm text-neutral-600">
            {lesson.title}
          </div>
          
          <Button 
            onClick={() => onNavigateNext && onNavigateNext()}
            disabled={!onNavigateNext}
          >
            Next →
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function WeekViewer({
  week,
  activeSection = "overview",
  weekInfo,
  courseContext,
  onLoadLesson,
  onQuizComplete,
  onContinueToNextWeek,
  onSectionChange,
  onNavigateNext,
}: {
  week: any;
  activeSection?: string;
  weekInfo?: any;
  courseContext?: any;
  onLoadLesson?: (info: any) => Promise<any | null>;
  onQuizComplete?: (results: any, adaptationSummary?: any) => void;
  onContinueToNextWeek?: () => void;
  onSectionChange?: (section: string) => void;
  onNavigateNext?: () => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [lessonMap, setLessonMap] = useState<Record<string, Lesson>>({});
  
  if (!week) {
    return (
      <div className="text-sm text-neutral-600">
        Select a week to get started.
      </div>
    );
  }

  // Show different content based on active section
  if (activeSection === "overview") {
    return (
      <div className="space-y-6">
        <div className="prose prose-neutral max-w-none">
          <div dangerouslySetInnerHTML={{ __html: mdToHtml(week.overview || "") }} />
        </div>
      </div>
    );
  }

  if (activeSection === "activities") {
    return (
      <div className="space-y-6">
        <div className="prose prose-neutral max-w-none">
          <div dangerouslySetInnerHTML={{ __html: mdToHtml(week.activities || "") }} />
        </div>
        
        {/* Activities Navigation */}
        <div className="pt-6 border-t">
          <div className="flex items-center justify-between">
            <div className="text-sm text-neutral-600">
              Week {weekInfo?.week_number || 1} Activities
            </div>
            
            <Button 
              onClick={() => onNavigateNext && onNavigateNext()}
              disabled={!onNavigateNext}
            >
              Next →
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (activeSection === "resources") {
    return (
      <div className="space-y-6">
        <div className="prose prose-neutral max-w-none">
          <div dangerouslySetInnerHTML={{ __html: mdToHtml(week.resources || "") }} />
        </div>
        
        {/* Resources Navigation */}
        <div className="pt-6 border-t">
          <div className="flex items-center justify-between">
            <div className="text-sm text-neutral-600">
              Week {weekInfo?.week_number || 1} Additional Resources
            </div>
            
            <Button 
              onClick={() => onNavigateNext && onNavigateNext()}
              disabled={!onNavigateNext}
            >
              Next →
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (activeSection === "quiz") {
    return (
      <QuizComponent
        quiz={week.quiz || null}
        weekInfo={weekInfo}
        courseContext={courseContext}
        onQuizComplete={onQuizComplete || (() => {})}
        onContinueToNextWeek={onContinueToNextWeek}
      />
    );
  }

  // Show individual lesson content
  const lesson = week.lesson_topics?.find((l: any) => l.id === activeSection);
  if (lesson) {
    return (
      <LessonComponent 
        lesson={lesson} 
        onLoadLesson={onLoadLesson}
        weekInfo={weekInfo}
        onNavigateNext={onNavigateNext}
      />
    );
  }

  // Default to overview
  return (
    <div className="space-y-6">
      <div className="prose prose-neutral max-w-none">
        <div dangerouslySetInnerHTML={{ __html: mdToHtml(week.overview || "") }} />
      </div>
    </div>
  );
}

// Simple markdown-to-HTML helper
function mdToHtml(md: string) {
  if (!md) return "";
  
  let html = md;
  
  // Headers
  html = html.replace(/^###\s(.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^##\s(.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^#\s(.+)$/gm, "<h1>$1</h1>");
  
  // Bold and italic
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  
  // Simple list handling
  const lines = html.split('\n');
  const processedLines = [];
  let inList = false;
  
  for (const line of lines) {
    if (line.match(/^\s*[-*]\s(.+)$/)) {
      if (!inList) {
        processedLines.push('<ul>');
        inList = true;
      }
      processedLines.push(`<li>${line.replace(/^\s*[-*]\s/, '')}</li>`);
    } else {
      if (inList) {
        processedLines.push('</ul>');
        inList = false;
      }
      processedLines.push(line);
    }
  }
  
  if (inList) {
    processedLines.push('</ul>');
  }
  
  // Join and handle paragraphs
  html = processedLines.join('\n');
  html = html.replace(/\n\n+/g, '</p><p>');
  html = `<p>${html}</p>`;
  
  // Clean up
  html = html.replace(/<p>(<h[1-6]>.*?<\/h[1-6]>)<\/p>/g, "$1");
  html = html.replace(/<p>(<ul>.*?<\/ul>)<\/p>/g, "$1");
  html = html.replace(/<p><\/p>/g, "");
  
  return html;
}
