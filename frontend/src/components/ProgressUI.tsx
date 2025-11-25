/**
 * Progress UI - Displays repository processing progress
 */

import {type TaskStatus} from "@/hooks/query/task";

interface ProgressUIProps {
  task: TaskStatus | undefined;
  repositoryName?: string;
}

export default function ProgressUI({task, repositoryName}: ProgressUIProps) {
  if (!task) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--bg-primary)]">
        <div className="text-center space-y-4">
          <div className="animate-spin h-12 w-12 border-4 border-purple-500 border-t-transparent rounded-full mx-auto"></div>
          <p className="text-[var(--text-secondary)]">Loading repository...</p>
        </div>
      </div>
    );
  }

  const {progress, status} = task;

  // Map step names to user-friendly labels (matches backend TaskStep enum)
  const stepLabels: Record<string, string> = {
    queued: "Queued",
    fetching: "Fetching files from GitHub",
    parsing: "Parsing code structure",
    embedding: "Generating embeddings",
    summarizing: "Generating AI summaries",
    overview: "Generating repository overview",
    finalizing: "Finalizing analysis",
    completed: "Completed",
  };

  const currentStep = progress?.current_step ?? "queued";
  const currentStepLabel = stepLabels[currentStep] || currentStep;

  // Calculate overall progress based on current step + file progress
  const calculateProgressPercentage = (): number => {
    const fileProgress =
      (progress?.total_files ?? 0) > 0
        ? ((progress?.processed_files ?? 0) / (progress?.total_files ?? 1)) * 100
        : 0;

    // Progress ranges for each step:
    // QUEUED: 0%
    // PARSING: 0-60% (based on file progress)
    // EMBEDDING: 60-80%
    // OVERVIEW: 80-95%
    // FINALIZING: 95-98%
    // COMPLETED: 100%

    switch (currentStep) {
      case "queued":
        return 0;
      case "fetching":
        return 5;
      case "parsing":
        // File parsing: 5% to 60%
        return Math.round(5 + (fileProgress * 0.55));
      case "embedding":
        return 70;
      case "summarizing":
        return 75;
      case "overview":
        return 85;
      case "finalizing":
        return 95;
      case "completed":
        return 100;
      default:
        return 0;
    }
  };

  const progressPercentage = calculateProgressPercentage();

  return (
    <div className="flex items-center justify-center min-h-screen bg-[var(--bg-primary)] px-4">
      <div className="max-w-2xl w-full">
        <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-2xl p-8 space-y-6">
          {/* Header */}
          <div className="text-center space-y-2">
            <h2 className="text-2xl font-semibold text-[var(--text-primary)]">
              Processing Repository
            </h2>
            {repositoryName && (
              <p className="text-[var(--text-secondary)]">{repositoryName}</p>
            )}
          </div>

          {/* Status Badge */}
          <div className="flex justify-center">
            <div className="inline-flex items-center space-x-2 bg-purple-500/10 text-purple-400 px-4 py-2 rounded-full text-sm">
              <div className="animate-spin h-4 w-4 border-2 border-purple-400 border-t-transparent rounded-full"></div>
              <span className="capitalize">{status.replace("_", " ")}</span>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-[var(--text-secondary)]">
                {currentStepLabel}
              </span>
              <span className="text-[var(--text-primary)] font-medium">
                {progress?.processed_files ?? 0} / {progress?.total_files ?? 0} files
              </span>
            </div>

            {/* Progress bar container */}
            <div className="relative h-3 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
              {/* Animated background gradient */}
              <div
                className="absolute inset-0 bg-gradient-to-r from-purple-500 via-pink-500 to-purple-500 bg-[length:200%_100%] animate-[shimmer_2s_infinite]"
                style={{width: `${progressPercentage}%`}}
              ></div>
            </div>

            {/* Percentage */}
            <div className="text-center">
              <span className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
                {progressPercentage}%
              </span>
            </div>
          </div>

          {/* Step Details */}
          <div className="grid grid-cols-5 gap-3 pt-4">
            <StepIndicator
              label="Parsing"
              active={currentStep === "parsing"}
              completed={["embedding", "summarizing", "overview", "finalizing", "completed"].includes(currentStep)}
            />
            <StepIndicator
              label="Embedding"
              active={currentStep === "embedding" || currentStep === "summarizing"}
              completed={["overview", "finalizing", "completed"].includes(currentStep)}
            />
            <StepIndicator
              label="Overview"
              active={currentStep === "overview"}
              completed={["finalizing", "completed"].includes(currentStep)}
            />
            <StepIndicator
              label="Finalizing"
              active={currentStep === "finalizing"}
              completed={currentStep === "completed"}
            />
            <StepIndicator
              label="Complete"
              active={false}
              completed={currentStep === "completed"}
            />
          </div>

          {/* Info Message */}
          <div className="text-center pt-4">
            <p className="text-sm text-[var(--text-secondary)]">
              This may take a few minutes depending on repository size.
              <br />
              Feel free to refresh the page - progress is saved.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== Step Indicator ====================

interface StepIndicatorProps {
  label: string;
  active: boolean;
  completed: boolean;
}

function StepIndicator({label, active, completed}: StepIndicatorProps) {
  return (
    <div className="flex flex-col items-center space-y-2">
      <div
        className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
          completed
            ? "bg-green-500/20 text-green-400 border-2 border-green-500"
            : active
            ? "bg-purple-500/20 text-purple-400 border-2 border-purple-500 animate-pulse"
            : "bg-[var(--bg-tertiary)] text-gray-500 border-2 border-gray-700"
        }`}
      >
        {completed ? (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        ) : (
          <div
            className={`w-2 h-2 rounded-full ${
              active ? "bg-purple-400" : "bg-gray-600"
            }`}
          ></div>
        )}
      </div>
      <span
        className={`text-xs font-medium ${
          completed || active ? "text-[var(--text-primary)]" : "text-gray-500"
        }`}
      >
        {label}
      </span>
    </div>
  );
}
