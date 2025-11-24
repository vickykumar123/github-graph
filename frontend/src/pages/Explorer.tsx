/**
 * Explorer Page - GitHub-style file tree + code viewer + file summary
 * Protected: Requires sessionId and repoId
 */

export default function Explorer() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      {/* Layout: File Tree (25%) | Code Viewer + Summary (75%) */}
      <div className="flex h-screen">
        {/* Left Sidebar - File Tree */}
        <div className="w-1/4 border-r border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 overflow-auto">
          <h2 className="text-lg font-semibold mb-4">Files</h2>
          <p className="text-sm text-[var(--text-secondary)]">
            GitHub-style file tree coming soon...
          </p>
        </div>

        {/* Right Panel - Code + Summary */}
        <div className="flex-1 flex flex-col">
          {/* Code Viewer */}
          <div className="flex-1 p-6 overflow-auto">
            <h2 className="text-xl font-semibold mb-4">Code Preview</h2>
            <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg p-4">
              <p className="text-[var(--text-secondary)]">
                Select a file from the tree to view its contents with syntax highlighting
              </p>
            </div>
          </div>

          {/* File Summary Section */}
          <div className="h-64 border-t border-[var(--border-color)] bg-[var(--bg-secondary)] p-6 overflow-auto">
            <h3 className="text-lg font-semibold mb-3">AI Summary</h3>
            <p className="text-sm text-[var(--text-secondary)]">
              AI-generated file summary will appear here when you select a file
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
