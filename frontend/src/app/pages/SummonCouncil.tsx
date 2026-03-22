import { useState, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router";
import { BrutalistButton } from "../components/BrutalistButton";
import { BrutalistCard } from "../components/BrutalistCard";
import { PhilosopherIcon } from "../components/PhilosopherIcon";
import {
  Check,
  ArrowLeft,
  Plus,
  Settings,
  X,
  MessageSquare,
  Loader2,
  Sparkles,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Pencil,
  Trash2,
  KeyRound,
} from "lucide-react";
import {
  getPersonas,
  recommendPanel,
  expandPersona,
  randomPersona,
  createPersona,
  updatePersona,
  deletePersona,
  createSession,
  getRuntimeConfig as fetchRuntimeConfig,
  setRuntimeConfig as saveRuntimeConfig,
  clearRuntimeConfig as clearRuntimeConfigRequest,
} from "../lib/api";
import type { Persona, PanelRecommendationResponse } from "../lib/types";
import { PHILOSOPHERS } from "../data/philosophers";

const PHILOSOPHER_META: Record<string, { era: string; stance: string; color: string }> = Object.fromEntries(
  PHILOSOPHERS.map((p) => [p.id, { era: p.era, stance: p.stance, color: p.color }])
);

const PHILOSOPHER_ORDER = ["socrates", "epicurus", "diogenes", "aristotle", "seneca", "marcus"];

// Tag → color, mapped to philosopher palette
const TAG_COLORS: Record<string, string> = {
  philosophy:   "#FF6B9D", // Socrates pink
  ethics:       "#FF6B9D",
  art:          "#E8FF8B", // Epicurus lime
  culture:      "#E8FF8B",
  psychology:   "#6B9DFF", // Diogenes blue
  science:      "#6B9DFF",
  creativity:   "#FF8B6B", // Aristotle salmon
  politics:     "#FF8B6B",
  spirituality: "#8B6BFF", // Seneca purple
  history:      "#FFB86B", // Marcus gold
};

export function SummonCouncil() {
  const location = useLocation();
  const navigate = useNavigate();
  const question: string = location.state?.question || sessionStorage.getItem("agora-question") || "";
  const context: string = location.state?.context || sessionStorage.getItem("agora-context") || "";
  const documentIds: string[] = location.state?.documentIds || [];

  // Personas from backend
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loadingPersonas, setLoadingPersonas] = useState(true);
  const [personasError, setPersonasError] = useState<string | null>(null);

  // Selection
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Panel recommendation
  const [recommendation, setRecommendation] = useState<PanelRecommendationResponse | null>(null);
  const [loadingRecommend, setLoadingRecommend] = useState(false);
  const [showRecommendation, setShowRecommendation] = useState(false);
  const [showDecisionFrame, setShowDecisionFrame] = useState(false);

  // Edit modal
  const [editingPersona, setEditingPersona] = useState<Persona | null>(null);
  const [editFields, setEditFields] = useState({ summary: "", identity_anchor: "", epistemic_style: "", argumentative_voice: "", opinion_change_threshold: "MODERATE" as "LOW" | "MODERATE" | "HIGH" });
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Custom persona builder
  const [showCustomBuilder, setShowCustomBuilder] = useState(false);
  const [customDescription, setCustomDescription] = useState("");
  const [expandedPersona, setExpandedPersona] = useState<Partial<Persona> | null>(null);
  const [loadingExpand, setLoadingExpand] = useState(false);
  const [loadingRandom, setLoadingRandom] = useState(false);
  const [savingPersona, setSavingPersona] = useState(false);
  const [customError, setCustomError] = useState<string | null>(null);

  // Debate parameters
  const [roundGoal, setRoundGoal] = useState(6);
  const [showSettings, setShowSettings] = useState(false);

  // Session creation
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [showRuntimeConfig, setShowRuntimeConfig] = useState(false);
  const [runtimeConfig, setRuntimeConfig] = useState({
    provider: "anthropic",
    model: "claude-haiku-4-5-20251001",
    selector_model: "",
    summary_model: "",
    base_url: "",
    api_key: "",
    api_key_set: false,
    source: "default" as "default" | "session",
  });
  const [runtimeNotice, setRuntimeNotice] = useState<string | null>(null);
  const [runtimeConfigLoading, setRuntimeConfigLoading] = useState(false);
  const [runtimeConfigError, setRuntimeConfigError] = useState<string | null>(null);
  const providerRequiresBaseUrl = runtimeConfig.provider.trim() === "openai-compatible-model";
  const hasApiKey = runtimeConfig.api_key.trim().length > 0 || runtimeConfig.api_key_set;
  const runtimeWarning = !runtimeConfig.provider.trim()
    ? "Choose an AI provider before using AI-powered personas, recommendations, or debates."
    : !runtimeConfig.model.trim()
      ? "Enter a model name before using AI features."
      : providerRequiresBaseUrl && !runtimeConfig.base_url.trim()
        ? "Enter a base URL for your OpenAI-compatible provider before using AI features."
        : !hasApiKey
          ? "Add an API key in API Provider before using AI features."
          : null;
  const aiReady = runtimeWarning === null;

  useEffect(() => {
    if (!question) {
      navigate("/", { replace: true });
      return;
    }
    setLoadingPersonas(true);
    Promise.allSettled([getPersonas(), fetchRuntimeConfig()])
      .then(([personasResult, runtimeResult]) => {
        if (personasResult.status === "fulfilled") {
          setPersonas(personasResult.value);
          setPersonasError(null);
        } else {
          setPersonasError(
            personasResult.reason instanceof Error ? personasResult.reason.message : "Failed to load personas"
          );
        }

        if (runtimeResult.status === "fulfilled") {
          const runtime = runtimeResult.value;
          setRuntimeConfig({
            provider: runtime.provider,
            model: runtime.model,
            selector_model: runtime.selector_model || "",
            summary_model: runtime.summary_model || "",
            base_url: runtime.base_url || "",
            api_key: "",
            api_key_set: runtime.api_key_set,
            source: runtime.source,
          });
          setRuntimeConfigError(null);
        } else {
          setRuntimeConfigError(
            runtimeResult.reason instanceof Error ? runtimeResult.reason.message : "Failed to load runtime config"
          );
        }
      })
      .finally(() => setLoadingPersonas(false));
  }, []);

  const refreshRuntimeConfig = async () => {
    try {
      const runtime = await fetchRuntimeConfig();
      setRuntimeConfig({
        provider: runtime.provider,
        model: runtime.model,
        selector_model: runtime.selector_model || "",
        summary_model: runtime.summary_model || "",
        base_url: runtime.base_url || "",
        api_key: "",
        api_key_set: runtime.api_key_set,
        source: runtime.source,
      });
      setRuntimeConfigError(null);
    } catch (e) {
      setRuntimeConfigError(e instanceof Error ? e.message : "Failed to load runtime config");
    }
  };

  const togglePersona = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  };

  const handleDeletePersona = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Delete this persona? This cannot be undone.")) return;
    try {
      await deletePersona(id);
      setPersonas((prev) => prev.filter((p) => p.id !== id));
      setSelectedIds((prev) => prev.filter((sid) => sid !== id));
    } catch {
      // ignore
    }
  };

  const openEdit = (persona: Persona, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingPersona(persona);
    setEditFields({
      summary: persona.summary,
      identity_anchor: persona.identity_anchor,
      epistemic_style: persona.epistemic_style,
      argumentative_voice: persona.argumentative_voice,
      opinion_change_threshold: persona.opinion_change_threshold,
    });
    setEditError(null);
  };

  const handleSaveEdit = async () => {
    if (!editingPersona) return;
    setSavingEdit(true);
    setEditError(null);
    try {
      const updated = await updatePersona(editingPersona.id, editFields);
      setPersonas((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setEditingPersona(null);
    } catch (e) {
      setEditError(`Save failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleRecommend = async () => {
    if (!aiReady) {
      setCreateError(runtimeWarning ?? "Configure API Provider before requesting an AI recommendation.");
      return;
    }
    setLoadingRecommend(true);
    setCreateError(null);
    try {
      const rec = await recommendPanel(question, 5, documentIds);
      setRecommendation(rec);
      setShowRecommendation(true);
      setSelectedIds(rec.suggested_ids);
    } catch (e) {
      setCreateError(`Recommendation failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setLoadingRecommend(false);
    }
  };

  const handleRandomPersona = async () => {
    if (!aiReady) {
      setCustomError(runtimeWarning ?? "Configure API Provider before generating personas with AI.");
      return;
    }
    setCustomError(null);
    setLoadingRandom(true);
    try {
      const result = await randomPersona();
      setCustomDescription(result.seed_description ?? "");
      setExpandedPersona(result);
    } catch (e) {
      setCustomError(`Random failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setLoadingRandom(false);
    }
  };

  const handleExpandPersona = async () => {
    if (!aiReady) {
      setCustomError(runtimeWarning ?? "Configure API Provider before expanding personas with AI.");
      return;
    }
    if (customDescription.trim().length < 12) {
      setCustomError("Description must be at least 12 characters");
      return;
    }
    setCustomError(null);
    setLoadingExpand(true);
    try {
      const expanded = await expandPersona(customDescription);
      setExpandedPersona(expanded);
    } catch (e) {
      setCustomError(`Expand failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setLoadingExpand(false);
    }
  };

  const handleDirectSave = async () => {
    const desc = customDescription.trim();
    if (desc.length < 12) {
      setCustomError("Description must be at least 12 characters");
      return;
    }
    setSavingPersona(true);
    setCustomError(null);
    try {
      const saved = await createPersona({
        name: desc.length > 60 ? desc.slice(0, 57) + "..." : desc,
        summary: desc,
        identity_anchor: `You are ${desc}.`,
        epistemic_style: "practical and direct",
        argumentative_voice: "straightforward",
        tags: [],
        opinion_change_threshold: "MODERATE",
        avatar_emoji: "",
        visibility: "private",
        creator_id: "local-user",
        cognitive_biases: [],
      });
      setPersonas((prev) => [...prev, saved]);
      setSelectedIds((prev) => [...prev, saved.id]);
      setShowCustomBuilder(false);
      setCustomDescription("");
      setExpandedPersona(null);
    } catch (e) {
      setCustomError(
        e instanceof Error && e.message.includes("already exists")
          ? "A persona with that name already exists. Try a different description."
          : `Save failed: ${e instanceof Error ? e.message : "Unknown error"}`
      );
    } finally {
      setSavingPersona(false);
    }
  };

  const handleSaveCustomPersona = async () => {
    if (!expandedPersona) return;
    setSavingPersona(true);
    setCustomError(null);
    try {
      const saved = await createPersona({
        name: expandedPersona.name ?? "Custom Agent",
        summary: expandedPersona.summary ?? customDescription,
        identity_anchor: expandedPersona.identity_anchor ?? customDescription,
        epistemic_style: expandedPersona.epistemic_style ?? "analytical",
        argumentative_voice: expandedPersona.argumentative_voice ?? "direct",
        tags: expandedPersona.tags ?? [],
        opinion_change_threshold: expandedPersona.opinion_change_threshold ?? "MODERATE",
        avatar_emoji: expandedPersona.avatar_emoji ?? "",
        visibility: "private",
        creator_id: "local-user",
        cognitive_biases: expandedPersona.cognitive_biases ?? [],
      });
      setPersonas((prev) => [...prev, saved]);
      setSelectedIds((prev) => [...prev, saved.id]);
      setShowCustomBuilder(false);
      setCustomDescription("");
      setExpandedPersona(null);
    } catch (e) {
      setCustomError(
        e instanceof Error && e.message.includes("already exists")
          ? "A persona with that name already exists. Try a different name."
          : `Save failed: ${e instanceof Error ? e.message : "Unknown error"}`
      );
    } finally {
      setSavingPersona(false);
    }
  };

  const handleStartDebate = async () => {
    if (selectedIds.length < 3) return;
    if (!aiReady) {
      setCreateError(runtimeWarning ?? "Configure API Provider before starting a debate.");
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const snapshot = await createSession(question, selectedIds, roundGoal, documentIds);
      sessionStorage.setItem("agora-question", question);
      navigate(`/debate/${snapshot.session_id}`, {
        state: { snapshot, question },
      });
    } catch (e) {
      setCreateError(`Failed to start debate: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setCreating(false);
    }
  };

  const handleSaveRuntimeConfig = async () => {
    if (!aiReady) {
      setRuntimeConfigError(runtimeWarning ?? "Complete the API Provider form before saving.");
      return;
    }
    setRuntimeConfigLoading(true);
    setRuntimeConfigError(null);
    setRuntimeNotice(null);
    try {
      await saveRuntimeConfig({
        provider: runtimeConfig.provider.trim(),
        model: runtimeConfig.model.trim(),
        selector_model: runtimeConfig.selector_model.trim() || null,
        summary_model: runtimeConfig.summary_model.trim() || null,
        base_url: runtimeConfig.base_url.trim() || null,
        api_key: runtimeConfig.api_key.trim() || undefined,
      });
      await refreshRuntimeConfig();
      setRuntimeNotice("Runtime configuration saved for this browser session.");
    } catch (e) {
      setRuntimeConfigError(`Failed to save config: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setRuntimeConfigLoading(false);
    }
  };

  const handleClearRuntimeConfig = async () => {
    setRuntimeConfigLoading(true);
    setRuntimeConfigError(null);
    setRuntimeNotice(null);
    try {
      await clearRuntimeConfigRequest();
      await refreshRuntimeConfig();
      setRuntimeNotice("Runtime configuration cleared. AI features stay disabled until you configure a provider and API key.");
    } catch (e) {
      setRuntimeConfigError(`Failed to clear config: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setRuntimeConfigLoading(false);
    }
  };

  // Group personas: philosophers first (known IDs), then custom
  const philosopherPersonas = personas
    .filter((p) => PHILOSOPHER_META[p.id])
    .sort((a, b) => {
      const ai = PHILOSOPHER_ORDER.indexOf(a.id);
      const bi = PHILOSOPHER_ORDER.indexOf(b.id);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });
  const customPersonas = personas.filter((p) => !PHILOSOPHER_META[p.id]);

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-5xl mx-auto">
        {/* Back */}
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 mb-6 hover:translate-x-[-2px] transition-transform"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </button>

        {/* Question Display */}
        <BrutalistCard variant="secondary" className="p-6 mb-6">
          <h2 className="mb-2">Your Question:</h2>
          <p className="text-lg">{question || "No question provided"}</p>
          {context && (
            <div className="mt-3 pt-3 border-t-2 border-black/20">
              <p className="text-sm text-muted-foreground mb-1">Context:</p>
              <p className="text-sm">{context}</p>
            </div>
          )}
          {documentIds.length > 0 && (
            <p className="text-xs text-muted-foreground mt-2">
              {documentIds.length} document{documentIds.length !== 1 ? "s" : ""} attached
            </p>
          )}
        </BrutalistCard>

        {/* Header row */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h2 className="mb-1">Choose your council</h2>
            <p className="text-muted-foreground text-sm">
              Select at least 3 debaters. Each is an independent LLM agent that reasons, takes positions, and argues from its own perspective.
            </p>
          </div>
          <div className="flex gap-2 flex-wrap justify-end">
            <BrutalistButton
              variant="accent"
              size="sm"
              onClick={handleRecommend}
              disabled={loadingRecommend || !aiReady}
            >
              {loadingRecommend ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Thinking...</>
              ) : (
                <><Sparkles className="w-4 h-4 mr-2" /> Recommend Panel</>
              )}
            </BrutalistButton>
            <BrutalistButton
              variant="terracotta"
              size="sm"
              onClick={() => setShowSettings(!showSettings)}
            >
              <Settings className="w-4 h-4 mr-2" />
              Parameters
            </BrutalistButton>
            <BrutalistButton
              variant="secondary"
              size="sm"
              onClick={() => setShowRuntimeConfig((current) => !current)}
            >
              <KeyRound className="w-4 h-4 mr-2" />
              API Provider
            </BrutalistButton>
          </div>
        </div>

        {runtimeConfigError && (
          <BrutalistCard className="p-4 mb-4 border-red-400 bg-red-50 text-red-700">
            <p className="text-sm">Runtime config issue: {runtimeConfigError}</p>
          </BrutalistCard>
        )}
        {runtimeNotice && (
          <BrutalistCard className="p-4 mb-4 border-green-500 bg-green-50 text-green-800">
            <p className="text-sm">{runtimeNotice}</p>
          </BrutalistCard>
        )}
        {runtimeWarning && (
          <BrutalistCard className="p-4 mb-4 border-amber-500 bg-amber-50 text-amber-900">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              <p className="text-sm">{runtimeWarning}</p>
            </div>
          </BrutalistCard>
        )}

        {showRuntimeConfig && (
          <BrutalistCard className="p-6 mb-6">
            <h3 className="mb-4 font-semibold">Runtime LLM settings</h3>
            <p className="text-sm text-muted-foreground mb-4">
              This is your local browser session only. Keys are sent to the backend and never returned. The stub provider is disabled.
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-black/60 block mb-1">Provider</label>
                <select
                  value={runtimeConfig.provider}
                  onChange={(e) => setRuntimeConfig((prev) => ({ ...prev, provider: e.target.value }))}
                  className="w-full border-2 border-black p-2 bg-white"
                >
                  <option value="">Choose provider</option>
                  <option value="anthropic">anthropic</option>
                  <option value="openai-compatible-model">openai-compatible-model</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-black/60 block mb-1">Model</label>
                <input
                  value={runtimeConfig.model}
                  onChange={(e) => setRuntimeConfig((prev) => ({ ...prev, model: e.target.value }))}
                  className="w-full border-2 border-black p-2 bg-white"
                  placeholder={runtimeConfig.provider === "anthropic" ? "claude-sonnet-4-5" : "Enter model name"}
                />
              </div>
              <div>
                <label className="text-xs text-black/60 block mb-1">Selector model (optional)</label>
                <input
                  value={runtimeConfig.selector_model}
                  onChange={(e) => setRuntimeConfig((prev) => ({ ...prev, selector_model: e.target.value }))}
                  className="w-full border-2 border-black p-2 bg-white"
                  placeholder="Leave empty to use default"
                />
              </div>
              <div>
                <label className="text-xs text-black/60 block mb-1">Summary model (optional)</label>
                <input
                  value={runtimeConfig.summary_model}
                  onChange={(e) => setRuntimeConfig((prev) => ({ ...prev, summary_model: e.target.value }))}
                  className="w-full border-2 border-black p-2 bg-white"
                  placeholder="Leave empty to use default"
                />
              </div>
              <div>
                <label className="text-xs text-black/60 block mb-1">OpenAI-compatible base URL (optional)</label>
                <input
                  value={runtimeConfig.base_url}
                  onChange={(e) => setRuntimeConfig((prev) => ({ ...prev, base_url: e.target.value }))}
                  className="w-full border-2 border-black p-2 bg-white"
                  placeholder="e.g. https://api.openai.com/v1"
                />
              </div>
              <div>
                <label className="text-xs text-black/60 block mb-1">API key</label>
                <input
                  type="password"
                  value={runtimeConfig.api_key}
                  onChange={(e) => setRuntimeConfig((prev) => ({ ...prev, api_key: e.target.value }))}
                  className="w-full border-2 border-black p-2 bg-white"
                  placeholder={runtimeConfig.api_key_set ? "Stored key exists for this session" : "Enter API key"}
                />
                <p className="text-xs text-black/50 mt-1">
                  Current status: {runtimeConfig.source === "session" ? "Session override" : "Server defaults"}.
                  {runtimeConfig.api_key_set ? " API key is configured." : " No API key configured."}
                </p>
              </div>
              <div className="flex gap-2 pt-2">
                <BrutalistButton
                  size="sm"
                  variant="accent"
                  onClick={handleSaveRuntimeConfig}
                  disabled={runtimeConfigLoading}
                >
                  {runtimeConfigLoading ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</>
                  ) : (
                    "Save session config"
                  )}
                </BrutalistButton>
                <BrutalistButton
                  size="sm"
                  variant="secondary"
                  onClick={handleClearRuntimeConfig}
                  disabled={runtimeConfigLoading}
                >
                  Clear session override
                </BrutalistButton>
              </div>
            </div>
          </BrutalistCard>
        )}

        {/* AI Recommendation Banner */}
        {showRecommendation && recommendation && (
          <BrutalistCard className="p-5 mb-6 bg-[#E8FF8B]">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                <h4 className="font-semibold text-sm">AI Panel Recommendation</h4>
              </div>
              <button onClick={() => setShowRecommendation(false)}>
                <X className="w-4 h-4" />
              </button>
            </div>
            {recommendation.selection_notice && (
              <p className="text-xs mb-2 text-black/60">{recommendation.selection_notice}</p>
            )}
            {recommendation.blind_spot_message && (
              <p className="text-sm mb-3">
                <span className="font-semibold">One thing to watch: </span>
                {recommendation.blind_spot_message}
              </p>
            )}
            <div className="space-y-2">
              {recommendation.recommendations.map((rec) => (
                <div key={rec.persona.id} className="flex items-start gap-2">
                  <PhilosopherIcon philosopherId={rec.persona.id} className="w-5 h-5 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold">{rec.persona.name}</p>
                    <p className="text-xs text-black/60">{rec.reasons[0]}</p>
                  </div>
                </div>
              ))}
            </div>
          </BrutalistCard>
        )}

        {/* Settings Panel */}
        {showSettings && (
          <BrutalistCard className="p-6 mb-6 bg-[#F0EDE6]">
            <h3 className="mb-4 font-semibold">Debate Parameters</h3>
            <div>
              <label className="flex items-center gap-2 mb-3 text-sm">
                <MessageSquare className="w-4 h-4" />
                Rounds of debate
              </label>
              <div>
                <div className="flex items-center gap-4">
                  <div className="flex-1 relative h-4 flex items-center">
                    <div className="absolute w-full h-3 bg-white border-2 border-black" />
                    <div
                      className="absolute h-3 border-y-2 border-l-2 border-black pointer-events-none"
                      style={{
                        width: `${((roundGoal - 3) / (8 - 3)) * 100}%`,
                        backgroundColor: "#FF6B9D",
                      }}
                    />
                    <input
                      type="range"
                      min="3"
                      max="8"
                      value={roundGoal}
                      onChange={(e) => setRoundGoal(Number(e.target.value))}
                      className="absolute w-full opacity-0 cursor-pointer h-6 z-10"
                    />
                    <div
                      className="absolute w-5 h-5 bg-white border-[3px] border-black shadow-[2px_2px_0_0_#0A0A0A] pointer-events-none"
                      style={{ left: `calc(${((roundGoal - 3) / (8 - 3)) * 100}% - 10px)` }}
                    />
                  </div>
                  <span className="bg-black text-white border-[3px] border-black shadow-[2px_2px_0_0_#0A0A0A] px-3 py-1 text-sm min-w-[80px] text-center tabular-nums">
                    {roundGoal} rounds
                  </span>
                </div>
                <div className="flex justify-between mt-1.5" style={{ paddingRight: "calc(80px + 1rem)" }}>
                  {[3, 5, 6, 8].map((v) => (
                    <span key={v} className="text-[10px] text-black/40">{v}</span>
                  ))}
                </div>
              </div>
            </div>
          </BrutalistCard>
        )}

        {/* Classical Philosophers Grid */}
        {loadingPersonas ? (
          <div className="flex items-center justify-center py-16 gap-3">
            <Loader2 className="w-6 h-6 animate-spin" />
            <span>Loading personas from server...</span>
          </div>
        ) : personasError ? (
          <BrutalistCard className="p-6 mb-6 bg-red-50 border-red-500">
            <div className="flex items-center gap-2 text-red-700">
              <AlertCircle className="w-5 h-5" />
              <p className="font-semibold">Could not load personas</p>
            </div>
            <p className="text-sm text-red-600 mt-1">{personasError}</p>
            <p className="text-xs text-red-500 mt-2">
              Make sure the backend is running: <code>uvicorn backend.app.main:app --reload</code>
            </p>
          </BrutalistCard>
        ) : (
          <>
            {/* Philosopher cards */}
            {philosopherPersonas.length > 0 && (
              <div className="mb-8">
                <h3 className="mb-4 font-bold">Classical Philosophers</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {philosopherPersonas.map((persona) => {
                    const isSelected = selectedIds.includes(persona.id);
                    const meta = PHILOSOPHER_META[persona.id];
                    return (
                      <PhilosopherCard
                        key={persona.id}
                        persona={persona}
                        meta={meta}
                        isSelected={isSelected}
                        onToggle={() => togglePersona(persona.id)}
                        onEdit={(e) => openEdit(persona, e)}
                      />
                    );
                  })}
                </div>
              </div>
            )}

            {/* Custom personas */}
            {customPersonas.length > 0 && (
              <div className="mb-8">
                <h3 className="mb-4 font-bold">Custom Personas</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {customPersonas.map((persona) => {
                    const isSelected = selectedIds.includes(persona.id);
                    return (
                      <CustomPersonaCard
                        key={persona.id}
                        persona={persona}
                        isSelected={isSelected}
                        onToggle={() => togglePersona(persona.id)}
                        onEdit={(e) => openEdit(persona, e)}
                        onDelete={(e) => handleDeletePersona(persona.id, e)}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}

        {/* Custom Persona Builder */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Create Custom Persona</h3>
            <BrutalistButton
              variant="terracotta"
              size="sm"
              onClick={() => {
                setShowCustomBuilder(!showCustomBuilder);
                setExpandedPersona(null);
                setCustomDescription("");
                setCustomError(null);
              }}
            >
              <Plus className="w-4 h-4 mr-2" />
              {showCustomBuilder ? "Cancel" : "New Persona"}
            </BrutalistButton>
          </div>

          {showCustomBuilder && (
            <BrutalistCard className="p-6 bg-[#F0EDE6]">
              <h4 className="font-semibold mb-4">Describe Your Agent</h4>
              <p className="text-sm text-muted-foreground mb-4">
                Describe any person, character, or archetype — real or fictional. The AI will expand it into a full debate persona, or not.
              </p>

              <div className="mb-4">
                <label className="block text-sm mb-2">Description (min 12 characters) *</label>
                <textarea
                  value={customDescription}
                  onChange={(e) => setCustomDescription(e.target.value)}
                  placeholder={"E.g., \"A poet who lost their faith and found something stranger\" or \"A marine biologist who thinks the ocean knows things we don't\""}
                  className="w-full p-3 border-2 border-black bg-white resize-none focus:outline-none focus:ring-4 focus:ring-black/20"
                  rows={3}
                />
              </div>

              {customError && (
                <div className="mb-4 p-3 bg-red-100 border-2 border-red-500 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-red-500" />
                  <p className="text-sm text-red-700">{customError}</p>
                </div>
              )}

              {expandedPersona && (
                <BrutalistCard className="p-4 mb-4 bg-white">
                  <div className="flex items-center gap-3 mb-3">
                    <PhilosopherIcon className="w-10 h-10" />
                    <div>
                      <p className="font-semibold">{expandedPersona.name}</p>
                      <p className="text-xs text-muted-foreground">{expandedPersona.epistemic_style}</p>
                    </div>
                  </div>
                  <p className="text-sm mb-2">{expandedPersona.summary}</p>
                  {expandedPersona.tags && expandedPersona.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {expandedPersona.tags.map((tag) => (
                        <span
                          key={tag}
                          className="text-xs px-2 py-0.5 font-semibold border-2 border-black"
                          style={{ backgroundColor: TAG_COLORS[tag] ?? "#E8FF8B" }}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </BrutalistCard>
              )}

              <div className="flex justify-end gap-3 flex-wrap">
                {!expandedPersona ? (
                  <>
                  <BrutalistButton
                    variant="secondary"
                    size="sm"
                    onClick={handleRandomPersona}
                    disabled={loadingRandom || loadingExpand || savingPersona || !aiReady}
                  >
                    {loadingRandom ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Conjuring...</>
                    ) : (
                      "Go Random"
                    )}
                  </BrutalistButton>
                  <BrutalistButton
                    variant="grey"
                    size="sm"
                    onClick={handleDirectSave}
                    disabled={savingPersona || loadingExpand || loadingRandom || customDescription.trim().length < 12}
                  >
                    {savingPersona ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</>
                    ) : (
                      "Add directly"
                    )}
                  </BrutalistButton>
                  <BrutalistButton
                    variant="accent"
                    size="sm"
                    onClick={handleExpandPersona}
                    disabled={loadingExpand || loadingRandom || savingPersona || customDescription.trim().length < 12 || !aiReady}
                  >
                    {loadingExpand ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Expanding...</>
                    ) : (
                      <><Sparkles className="w-4 h-4 mr-2" /> Expand with AI</>
                    )}
                  </BrutalistButton>
                  </>
                ) : (
                  <>
                    <BrutalistButton
                      variant="secondary"
                      size="sm"
                      onClick={() => setExpandedPersona(null)}
                    >
                      Re-expand
                    </BrutalistButton>
                    <BrutalistButton
                      variant="primary"
                      size="sm"
                      onClick={handleSaveCustomPersona}
                      disabled={savingPersona}
                    >
                      {savingPersona ? (
                        <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</>
                      ) : (
                        "Add to Council"
                      )}
                    </BrutalistButton>
                  </>
                )}
              </div>
            </BrutalistCard>
          )}

          {!showCustomBuilder && (
            <BrutalistCard className="p-6 text-center bg-[#F0EDE6] border-dashed">
              <p className="text-sm text-muted-foreground">
                Build custom LLM agents with unique personalities and debate styles... or go random!
              </p>
            </BrutalistCard>
          )}
        </div>

        {/* Decision frame collapsible */}
        {recommendation?.decision_frame && (
          <BrutalistCard className="p-4 mb-6 bg-[#F0EDE6]">
            <button
              className="flex items-center justify-between w-full"
              onClick={() => setShowDecisionFrame((v) => !v)}
            >
              <span className="text-sm font-semibold">Decision Frame (AI Analysis)</span>
              {showDecisionFrame ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            {showDecisionFrame && (
              <div className="mt-3 space-y-2 text-sm">
                <p><span className="font-semibold">Focus:</span> {recommendation.decision_frame.focus}</p>
                {recommendation.decision_frame.constraints.length > 0 && (
                  <p><span className="font-semibold">Constraints:</span> {recommendation.decision_frame.constraints.join("; ")}</p>
                )}
                {recommendation.decision_frame.unknowns.length > 0 && (
                  <p><span className="font-semibold">Unknowns:</span> {recommendation.decision_frame.unknowns.join("; ")}</p>
                )}
              </div>
            )}
          </BrutalistCard>
        )}

        {/* Error */}
        {createError && (
          <div className="mb-4 p-3 bg-red-100 border-2 border-red-500 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-500" />
            <p className="text-sm text-red-700">{createError}</p>
          </div>
        )}

        {/* Start Button */}
        <div className="flex flex-col items-center gap-2">
          <BrutalistButton
            variant="primary"
            size="lg"
            onClick={handleStartDebate}
            disabled={selectedIds.length < 3 || creating || !aiReady}
            className={selectedIds.length < 3 || !aiReady ? "opacity-50 cursor-not-allowed" : ""}
          >
            {creating ? (
              <>Creating session<AnimatedDots /></>
            ) : (
              `Begin Debate (${selectedIds.length} selected) →`
            )}
          </BrutalistButton>
          {selectedIds.length < 3 && selectedIds.length > 0 && (
            <p className="text-sm text-muted-foreground">
              Select {3 - selectedIds.length} more persona{3 - selectedIds.length !== 1 ? "s" : ""}
            </p>
          )}
          {selectedIds.length >= 3 && runtimeWarning && (
            <p className="text-sm text-muted-foreground">{runtimeWarning}</p>
          )}
          {selectedIds.length === 0 && (
            <p className="text-sm text-muted-foreground">Select at least 3 personas to begin</p>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      {editingPersona && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={() => setEditingPersona(null)}
        >
          <div
            className="bg-[#F5F0E8] border-[3px] border-black shadow-[6px_6px_0_0_#0A0A0A] w-full max-w-xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div
              className="flex items-center justify-between p-5 border-b-[3px] border-black"
              style={{
                backgroundColor: PHILOSOPHER_META[editingPersona.id]
                  ? `${PHILOSOPHER_META[editingPersona.id].color}80`
                  : "#F5F0E8",
              }}
            >
              <div className="flex items-center gap-3">
                <PhilosopherIcon philosopherId={editingPersona.id} className="w-8 h-8" />
                <div>
                  <h3 className="font-bold text-lg">{editingPersona.name}</h3>
                  {PHILOSOPHER_META[editingPersona.id] && (
                    <p className="text-xs text-muted-foreground">{PHILOSOPHER_META[editingPersona.id].era}</p>
                  )}
                </div>
              </div>
              <button
                onClick={() => setEditingPersona(null)}
                className="w-8 h-8 flex items-center justify-center border-2 border-black bg-white hover:bg-black hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal fields */}
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1">Summary</label>
                <textarea
                  value={editFields.summary}
                  onChange={(e) => setEditFields((f) => ({ ...f, summary: e.target.value }))}
                  className="w-full p-3 border-2 border-black bg-white resize-none focus:outline-none focus:ring-4 focus:ring-black/20 text-sm"
                  rows={3}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1">Identity Anchor</label>
                <textarea
                  value={editFields.identity_anchor}
                  onChange={(e) => setEditFields((f) => ({ ...f, identity_anchor: e.target.value }))}
                  className="w-full p-3 border-2 border-black bg-white resize-none focus:outline-none focus:ring-4 focus:ring-black/20 text-sm"
                  rows={3}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1">Epistemic Style</label>
                <textarea
                  value={editFields.epistemic_style}
                  onChange={(e) => setEditFields((f) => ({ ...f, epistemic_style: e.target.value }))}
                  className="w-full p-3 border-2 border-black bg-white resize-none focus:outline-none focus:ring-4 focus:ring-black/20 text-sm"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1">Argumentative Voice</label>
                <textarea
                  value={editFields.argumentative_voice}
                  onChange={(e) => setEditFields((f) => ({ ...f, argumentative_voice: e.target.value }))}
                  className="w-full p-3 border-2 border-black bg-white resize-none focus:outline-none focus:ring-4 focus:ring-black/20 text-sm"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1">Opinion Change Threshold</label>
                <div className="flex gap-2">
                  {(["LOW", "MODERATE", "HIGH"] as const).map((val) => (
                    <button
                      key={val}
                      onClick={() => setEditFields((f) => ({ ...f, opinion_change_threshold: val }))}
                      className={`flex-1 py-2 text-sm font-semibold border-2 border-black transition-colors ${
                        editFields.opinion_change_threshold === val
                          ? "bg-black text-white"
                          : "bg-white hover:bg-gray-100"
                      }`}
                    >
                      {val}
                    </button>
                  ))}
                </div>
              </div>

              {editError && (
                <div className="p-3 bg-red-100 border-2 border-red-500 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-red-500" />
                  <p className="text-sm text-red-700">{editError}</p>
                </div>
              )}
            </div>

            {/* Modal footer */}
            <div className="flex justify-end gap-3 p-5 border-t-[3px] border-black">
              <BrutalistButton variant="grey" size="sm" onClick={() => setEditingPersona(null)}>
                Cancel
              </BrutalistButton>
              <BrutalistButton variant="primary" size="sm" onClick={handleSaveEdit} disabled={savingEdit}>
                {savingEdit ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</> : "Save Changes"}
              </BrutalistButton>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Philosopher card (exact design match) ───────────────────────────────────

interface PhilosopherCardProps {
  persona: Persona;
  meta: { era: string; stance: string; color: string };
  isSelected: boolean;
  onToggle: () => void;
  onEdit: (e: React.MouseEvent) => void;
}

function PhilosopherCard({ persona, meta, isSelected, onToggle, onEdit }: PhilosopherCardProps) {
  return (
    <div
      onClick={onToggle}
      className={`relative bg-white border-black cursor-pointer transition-all p-5 ${
        isSelected
          ? "border-[4px] shadow-[6px_6px_0_0_#0A0A0A]"
          : "border-[3px] shadow-[4px_4px_0_0_#0A0A0A] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0_0_#0A0A0A] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none"
      }`}
    >
      {/* Top-right button: check when selected, pencil when not */}
      {isSelected ? (
        <button
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
          className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center border-2 border-black bg-black text-white"
        >
          <Check className="w-4 h-4" />
        </button>
      ) : (
        <button
          onClick={onEdit}
          className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center border-2 border-black bg-white hover:bg-black hover:text-white transition-colors"
        >
          <Pencil className="w-3.5 h-3.5" />
        </button>
      )}

      {/* Icon + Name row */}
      <div className="flex items-start gap-3 mb-3 pr-10">
        <PhilosopherIcon
          philosopherId={persona.id}
          className="w-12 h-12 flex-shrink-0"
        />
        <div>
          <h3 className="font-bold text-lg leading-tight">{persona.name}</h3>
          <p className="text-sm text-muted-foreground">{meta.era}</p>
        </div>
      </div>

      {/* Stance badge */}
      <div className="mb-3">
        <span
          className="inline-block px-3 py-1 text-sm font-semibold border-2 border-black"
          style={{ backgroundColor: meta.color }}
        >
          {meta.stance}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm leading-relaxed text-gray-800">{persona.summary}</p>
    </div>
  );
}

// ── Custom persona card ─────────────────────────────────────────────────────

interface CustomPersonaCardProps {
  persona: Persona;
  isSelected: boolean;
  onToggle: () => void;
  onEdit: (e: React.MouseEvent) => void;
  onDelete: (e: React.MouseEvent) => void;
}

function CustomPersonaCard({ persona, isSelected, onToggle, onEdit, onDelete }: CustomPersonaCardProps) {
  return (
    <div
      onClick={onToggle}
      className={`relative bg-white border-black cursor-pointer transition-all p-5 ${
        isSelected
          ? "border-[4px] shadow-[6px_6px_0_0_#0A0A0A]"
          : "border-[3px] shadow-[4px_4px_0_0_#0A0A0A] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0_0_#0A0A0A] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none"
      }`}
    >
      {/* Top-right action buttons */}
      <div className="absolute top-3 right-3 flex gap-1.5">
        {isSelected ? (
          <button
            onClick={(e) => { e.stopPropagation(); onToggle(); }}
            className="w-8 h-8 flex items-center justify-center border-2 border-black bg-black text-white"
          >
            <Check className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={onEdit}
            className="w-8 h-8 flex items-center justify-center border-2 border-black bg-white hover:bg-black hover:text-white transition-colors"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
        )}
        <button
          onClick={onDelete}
          className="w-8 h-8 flex items-center justify-center border-2 border-black bg-white hover:bg-red-500 hover:text-white hover:border-white transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex items-start gap-3 mb-3 pr-20">
        <PhilosopherIcon className="w-12 h-12 flex-shrink-0" />
        <div>
          <h3 className="font-bold text-lg leading-tight">{persona.name}</h3>
          <p className="text-xs text-muted-foreground">Custom</p>
        </div>
      </div>

      {persona.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {persona.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="inline-block px-2 py-0.5 text-xs font-semibold border-2 border-black"
              style={{ backgroundColor: TAG_COLORS[tag] ?? "#E8FF8B" }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <p className="text-sm leading-relaxed text-gray-800 line-clamp-3">{persona.summary}</p>
    </div>
  );
}

// ── Animated dots: cycles . → .. → ... → . ─────────────────────────────────

function AnimatedDots() {
  const [count, setCount] = useState(1);
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    ref.current = setInterval(() => setCount((c) => (c % 3) + 1), 400);
    return () => { if (ref.current) clearInterval(ref.current); };
  }, []);

  return <span style={{ display: "inline-block", width: "1.5ch", textAlign: "left" }}>{".".repeat(count)}</span>;
}
