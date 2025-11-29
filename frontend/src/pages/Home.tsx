/**
 * Home Page - Initialize session, hero section, GitHub URL input
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useInitializeSession, useUpdateSessionPreferences } from "@/hooks/query/session";
import { useCreateRepository } from "@/hooks/query/repository";
import { AI_PROVIDERS, getModelsForProvider, getDefaultModel } from "@/utils/providers";
import { getSessionIdFromStorage, saveApiKeyToStorage } from "@/utils/storage";

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
    const defaultModel = getDefaultModel(newProvider);
    setModel(defaultModel);
  };

  // Get available models for selected provider
  const availableModels = provider ? getModelsForProvider(provider) : [];

  // Initialize session on page load
  useEffect(() => {
    const setupSession = async () => {
      const existingId = getSessionIdFromStorage();
      if (existingId) {
        setSessionId(existingId);
        console.log("Using existing session:", existingId);
        return;
      }

      try {
        const session = await initSession();
        setSessionId(session.session_id);
      } catch (error) {
        console.error("Failed to initialize session:", error);
      }
    };

    setupSession();
  }, []);

  const canSubmit = githubUrl && apiKey && provider && model && sessionId;
  const isProcessing = isCreatingRepo;

  const handleSubmit = async () => {
    if (!canSubmit || !sessionId) return;

    setError(null);

    try {
      saveApiKeyToStorage(apiKey);

      await updateSessionPreferences({
        session_id: sessionId,
        ai_provider: provider,
        ai_model: model,
        theme: "dark",
      });

      const response = await createRepository({
        github_url: githubUrl,
        session_id: sessionId,
        api_key: apiKey,
      });

      navigate(`/explorer/${response.repo_id}`);
    } catch (err) {
      console.error("Failed to create repository:", err);
      setError(err instanceof Error ? err.message : "Failed to create repository");
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] overflow-hidden relative">
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden">
        {/* Gradient Orbs */}
        <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] bg-purple-600/30 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute top-[20%] right-[-15%] w-[500px] h-[500px] bg-pink-600/20 rounded-full blur-[100px] animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute bottom-[-10%] left-[30%] w-[400px] h-[400px] bg-blue-600/20 rounded-full blur-[80px] animate-pulse" style={{ animationDelay: '2s' }} />

        {/* Grid Pattern */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
            backgroundSize: '50px 50px'
          }}
        />
      </div>

      {/* Main Content */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center space-y-8">

          {/* Icon + Logo (Side by Side) */}
          <div className="relative inline-flex items-center gap-4 md:gap-6">
            {/* Custom Icon */}
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-purple-500 via-pink-500 to-purple-500 blur-xl opacity-60 animate-pulse" />
              <svg
                className="relative w-16 h-16 md:w-20 md:h-20"
                viewBox="0 0 100 100"
                fill="none"
              >
                {/* Background circle */}
                <circle cx="50" cy="50" r="45" className="fill-white/5 stroke-white/10" strokeWidth="1" />

                {/* Code brackets */}
                <path
                  d="M30 35 L20 50 L30 65"
                  className="stroke-purple-400"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                />
                <path
                  d="M70 35 L80 50 L70 65"
                  className="stroke-pink-400"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                />

                {/* Network nodes - representing dependency graph */}
                <circle cx="40" cy="40" r="5" className="fill-purple-400" />
                <circle cx="60" cy="40" r="5" className="fill-pink-400" />
                <circle cx="50" cy="55" r="6" className="fill-blue-400" />
                <circle cx="40" cy="68" r="4" className="fill-purple-400/70" />
                <circle cx="60" cy="68" r="4" className="fill-pink-400/70" />

                {/* Connecting lines */}
                <path
                  d="M40 45 L50 50 M60 45 L50 50 M50 61 L40 65 M50 61 L60 65"
                  className="stroke-white/30"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />

                {/* Walking path dots */}
                <circle cx="35" cy="50" r="1.5" className="fill-white/40" />
                <circle cx="50" cy="45" r="1.5" className="fill-white/40" />
                <circle cx="65" cy="50" r="1.5" className="fill-white/40" />
              </svg>
            </div>

            {/* Animated Title */}
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-purple-500 via-pink-500 to-purple-500 blur-2xl opacity-40 animate-pulse" />
              <h1 className="relative text-5xl md:text-7xl font-black bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 bg-clip-text text-transparent animate-gradient bg-[length:200%_auto]">
                GitWalk
              </h1>
            </div>
          </div>

          {/* Tagline */}
          <p className="text-xl text-gray-400 max-w-2xl mx-auto leading-relaxed">
            <span className="text-white font-medium">AI-powered</span> code exploration.
            Understand any repository in <span className="text-purple-400 font-medium">minutes</span>, not hours.
          </p>

          {/* How it works - Step by step */}
          <div className="flex flex-wrap justify-center items-center gap-4 md:gap-5 mt-4 text-sm">
            <div className="flex items-center gap-2 text-gray-400">
              <div className="w-7 h-7 rounded-full bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400 font-bold text-xs">1</div>
              <span>Paste GitHub URL</span>
            </div>
            <span className="text-gray-600 hidden md:inline">→</span>
            <div className="flex items-center gap-2 text-gray-400">
              <div className="w-7 h-7 rounded-full bg-pink-500/20 border border-pink-500/30 flex items-center justify-center text-pink-400 font-bold text-xs">2</div>
              <span>AI analyzes code</span>
            </div>
            <span className="text-gray-600 hidden md:inline">→</span>
            <div className="flex items-center gap-2 text-gray-400">
              <div className="w-7 h-7 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-xs">3</div>
              <span>Explore & chat</span>
            </div>
          </div>

          {/* Value proposition */}
          <p className="max-w-2xl mx-auto mt-3 text-gray-500 text-sm">
            No more getting lost in unfamiliar codebases. Ask questions like{" "}
            <span className="text-purple-400">"Where is authentication handled?"</span> or{" "}
            <span className="text-pink-400">"What does this function do?"</span>
          </p>

          {/* Session Status */}
          {isPending && (
            <div className="flex items-center justify-center space-x-3 text-gray-400">
              <div className="relative">
                <div className="w-5 h-5 border-2 border-purple-500/30 rounded-full" />
                <div className="absolute inset-0 w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              </div>
              <span>Initializing session...</span>
            </div>
          )}

          {sessionId && (
            <div className="inline-flex items-center space-x-2 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-5 py-2.5 rounded-full text-sm font-medium backdrop-blur-sm">
              <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              <span>Session Ready</span>
            </div>
          )}

          {/* Input Form Card */}
          <div className="mt-12 max-w-xl mx-auto">
            <div className="relative group">
              {/* Card glow effect */}
              <div className="absolute -inset-1 bg-gradient-to-r from-purple-600 via-pink-600 to-purple-600 rounded-3xl blur-lg opacity-25 group-hover:opacity-40 transition-opacity duration-500" />

              <div className="relative bg-[#12121a]/80 backdrop-blur-xl border border-white/10 rounded-2xl p-8 space-y-5">
                <div className="flex items-center justify-center space-x-2 mb-6">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500" />
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                  <span className="ml-4 text-gray-500 text-sm font-mono">new-analysis</span>
                </div>

                {/* Provider Selection */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-400 text-left">
                    AI Provider
                  </label>
                  <select
                    value={provider}
                    onChange={(e) => handleProviderChange(e.target.value)}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all hover:bg-white/[0.07]"
                  >
                    <option value="" className="bg-[#1a1a24]">Select Provider</option>
                    {AI_PROVIDERS.map((p) => (
                      <option key={p.id} value={p.id} className="bg-[#1a1a24]">
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Model Selection */}
                {provider && (
                  <div className="space-y-2 animate-fadeIn">
                    <label className="block text-sm font-medium text-gray-400 text-left">
                      Model
                    </label>
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all hover:bg-white/[0.07]"
                    >
                      {availableModels.map((m) => (
                        <option key={m.id} value={m.id} className="bg-[#1a1a24]">
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* API Key */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-400 text-left">
                    API Key
                  </label>
                  <div className="relative">
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="sk-..."
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all hover:bg-white/[0.07]"
                    />
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 text-left flex items-center gap-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                    </svg>
                    Stored locally, never sent to our servers
                  </p>
                </div>

                {/* GitHub URL */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-400 text-left">
                    GitHub Repository
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={githubUrl}
                      onChange={(e) => setGithubUrl(e.target.value)}
                      placeholder="https://github.com/owner/repo"
                      className="w-full px-4 py-3 pl-11 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all hover:bg-white/[0.07]"
                    />
                    <div className="absolute left-3 top-1/2 -translate-y-1/2">
                      <svg className="w-5 h-5 text-gray-500" fill="currentColor" viewBox="0 0 24 24">
                        <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0012 2z" />
                      </svg>
                    </div>
                  </div>
                </div>

                {/* Error Message */}
                {error && (
                  <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-xl text-sm flex items-center gap-2">
                    <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    {error}
                  </div>
                )}

                {/* Submit Button */}
                <button
                  onClick={handleSubmit}
                  disabled={!canSubmit || isProcessing}
                  className={`relative w-full py-4 px-6 rounded-xl font-semibold text-lg transition-all duration-300 overflow-hidden group ${
                    canSubmit && !isProcessing
                      ? "bg-gradient-to-r from-purple-500 via-pink-500 to-purple-500 bg-[length:200%_auto] hover:bg-right text-white shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 hover:scale-[1.02] active:scale-[0.98]"
                      : "bg-gray-800 text-gray-500 cursor-not-allowed"
                  }`}
                >
                  {isProcessing ? (
                    <span className="flex items-center justify-center space-x-3">
                      <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>Analyzing...</span>
                    </span>
                  ) : canSubmit ? (
                    <span className="flex items-center justify-center gap-2">
                      <span>Start Exploring</span>
                      <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                    </span>
                  ) : (
                    "Fill all fields to continue"
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Features Section */}
          <div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {[
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  </svg>
                ),
                title: "Deep Code Analysis",
                description: "AST parsing for 10+ languages. Extract functions, classes, and dependencies automatically.",
                color: "purple"
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                ),
                title: "Dependency Graph",
                description: "Interactive visualization showing how files connect. Understand architecture at a glance.",
                color: "pink"
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                ),
                title: "AI Chat",
                description: "Ask questions in plain English. Get instant answers with code references.",
                color: "blue"
              }
            ].map((feature, i) => (
              <div
                key={feature.title}
                className="group relative p-6 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-white/10 hover:bg-white/[0.04] transition-all duration-300 hover:-translate-y-1"
              >
                <div className={`inline-flex p-3 rounded-xl bg-${feature.color}-500/10 text-${feature.color}-400 mb-4 group-hover:scale-110 transition-transform`}>
                  {feature.icon}
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  {feature.title}
                </h3>
                <p className="text-sm text-gray-500 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="mt-20 text-gray-600 text-sm">
            Built with React, FastAPI, MongoDB & AI
          </div>
        </div>
      </div>

      {/* CSS for animations */}
      <style>{`
        @keyframes gradient {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        .animate-gradient {
          animation: gradient 3s ease infinite;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}
