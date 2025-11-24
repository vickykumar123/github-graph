/**
 * Home Page - Initialize session, hero section, GitHub URL input
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useInitializeSession, getSessionIdFromStorage, useUpdateSessionPreferences } from "@/hooks/query/session";
import { useCreateRepository } from "@/hooks/query/repository";
import { AI_PROVIDERS, getModelsForProvider, getDefaultModel } from "@/utils/providers";

export default function Home() {
  const navigate = useNavigate();
  const { initSession, isPending } = useInitializeSession();
  const { updateSessionPreferences } = useUpdateSessionPreferences();
  const { createRepository, isPending: isCreatingRepo } = useCreateRepository();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Update model when provider changes
  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    // Auto-select first model for the provider
    const defaultModel = getDefaultModel(newProvider);
    setModel(defaultModel);
  };

  // Get available models for selected provider
  const availableModels = provider ? getModelsForProvider(provider) : [];

  // Initialize session on page load
  useEffect(() => {
    const setupSession = async () => {
      // Check if already exists in localStorage
      const existingId = getSessionIdFromStorage();
      if (existingId) {
        setSessionId(existingId);
        console.log("📦 Using existing session:", existingId);
        return;
      }

      // Create new session
      try {
        const session = await initSession();
        setSessionId(session.session_id);
      } catch (error) {
        console.error("Failed to initialize session:", error);
      }
    };

    setupSession();
  }, []); // Run only once on mount

  // Check if submit button should be enabled
  const canSubmit = githubUrl && apiKey && provider && model && sessionId;
  const isProcessing = isCreatingRepo;

  const handleSubmit = async () => {
    if (!canSubmit || !sessionId) return;

    setError(null);

    try {
      console.log("🚀 Starting repository submission...");

      // Step 1: Update session preferences with provider/model
      console.log("1️⃣ Updating session preferences...");
      await updateSessionPreferences({
        session_id: sessionId,
        ai_provider: provider,
        ai_model: model,
        theme: "dark",
      });

      // Step 2: Create repository with API key
      console.log("2️⃣ Creating repository...");
      const response = await createRepository({
        github_url: githubUrl,
        session_id: sessionId,
        api_key: apiKey,
      });

      console.log("✅ Repository created successfully:", response);

      // Step 3: Navigate to Explorer page
      navigate(`/explorer/${response.repo_id}`);
    } catch (err) {
      console.error("❌ Failed to create repository:", err);
      setError(err instanceof Error ? err.message : "Failed to create repository");
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      {/* Hero Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center space-y-8">
          {/* Title */}
          <div>
            <h1 className="text-6xl font-bold bg-gradient-to-r from-purple-400 via-pink-500 to-purple-600 bg-clip-text text-transparent">
              GitWalk
            </h1>
            <p className="mt-6 text-xl text-[var(--text-secondary)] max-w-3xl mx-auto">
              AI-powered code analysis and exploration. Understand any repository
              with interactive dependency graphs and intelligent chat.
            </p>
          </div>

          {/* Session Status */}
          {isPending && (
            <div className="flex items-center justify-center space-x-3 text-[var(--text-secondary)]">
              <div className="animate-spin h-5 w-5 border-2 border-purple-500 border-t-transparent rounded-full"></div>
              <span>Initializing session...</span>
            </div>
          )}

          {sessionId && (
            <div className="inline-flex items-center space-x-2 bg-green-500/10 text-green-400 px-4 py-2 rounded-full text-sm">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <span>Session Ready</span>
            </div>
          )}

          {/* Input Form */}
          <div className="mt-12 max-w-2xl mx-auto">
            <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-2xl p-8 space-y-6">
              <h2 className="text-2xl font-semibold text-[var(--text-primary)]">
                Add Repository
              </h2>

              {/* Provider Selection */}
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  AI Provider
                </label>
                <select
                  value={provider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="">Select Provider</option>
                  {AI_PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Model Selection */}
              {provider && (
                <div>
                  <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                    Model
                  </label>
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="w-full px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    {availableModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                        {m.description && ` - ${m.description}`}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* API Key */}
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  API Key
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter your API key"
                  className="w-full px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <p className="mt-2 text-xs text-[var(--text-secondary)]">
                  Your API key is never stored on our servers
                </p>
              </div>

              {/* GitHub URL */}
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  GitHub Repository URL
                </label>
                <input
                  type="text"
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                  className="w-full px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Error Message */}
              {error && (
                <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm">
                  {error}
                </div>
              )}

              {/* Submit Button */}
              <button
                onClick={handleSubmit}
                disabled={!canSubmit || isProcessing}
                className={`w-full py-3 px-6 rounded-lg font-medium transition-all ${
                  canSubmit && !isProcessing
                    ? "bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-600 hover:to-pink-700 text-white"
                    : "bg-gray-700 text-gray-500 cursor-not-allowed"
                }`}
              >
                {isProcessing ? (
                  <span className="flex items-center justify-center space-x-2">
                    <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div>
                    <span>Processing...</span>
                  </span>
                ) : canSubmit ? (
                  "Analyze Repository"
                ) : (
                  "Fill all fields to continue"
                )}
              </button>
            </div>
          </div>

          {/* Features */}
          <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <div className="text-center p-6">
              <div className="text-4xl mb-4">🔍</div>
              <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                Code Analysis
              </h3>
              <p className="text-sm text-[var(--text-secondary)]">
                Deep AST parsing for Python, JavaScript, TypeScript, Go, and more
              </p>
            </div>
            <div className="text-center p-6">
              <div className="text-4xl mb-4">🕸️</div>
              <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                Dependency Graph
              </h3>
              <p className="text-sm text-[var(--text-secondary)]">
                Interactive D3.js visualization of file dependencies
              </p>
            </div>
            <div className="text-center p-6">
              <div className="text-4xl mb-4">💬</div>
              <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                AI Chat
              </h3>
              <p className="text-sm text-[var(--text-secondary)]">
                Ask questions about the codebase in natural language
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
