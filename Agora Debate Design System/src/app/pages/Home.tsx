import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router";
import { BrutalistButton } from "../components/BrutalistButton";
import { BrutalistCard } from "../components/BrutalistCard";
import { GreekIllustration } from "../components/GreekIllustration";
import { DesktopPet } from "../components/DesktopPet";
import { Sparkles, AlertCircle, Upload, X, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { uploadDocument, deleteDocument } from "../lib/api";
import type { UploadedDocument } from "../lib/types";
import bustLeft from "../../assets/bust-left.png";
import bustRight from "../../assets/bust-right.png";

const ALL_PHILOSOPHERS = ["aristotle", "Diogenes", "epicurus", "marcus", "seneca", "socrates", "1", "2", "3"];

function pickPets(count: number): { character: string; x: number; delay: number }[] {
  const shuffled = [...ALL_PHILOSOPHERS].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, count).map((character, i) => ({
    character,
    x: 10 + (i / (count - 1 || 1)) * 80, // spread across 10–90% of width
    delay: i * 600,
  }));
}

export function Home() {
  const pets = useMemo(() => pickPets(3), []);
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  const [hoveredColumn, setHoveredColumn] = useState<"left" | "right" | null>(null);
  const [leftPrompt, setLeftPrompt] = useState("");
  const [rightPrompt, setRightPrompt] = useState("");

  const thoughtPrompts = [
    "Hmmm, I wonder... is free will just an illusion?",
    "What if the cave was actually quite cosy?",
    "Could a hot dog be considered a sandwich?",
    "Is it better to be feared or loved?",
    "What does it mean to live a good life?",
    "If I know nothing, do I know that I know nothing?",
    "Would I rather be right, or be happy?",
    "What is the sound of one hand clapping?",
    "Are we living in a simulation right now?",
    "Should virtue be its own reward?",
    "Is democracy just mob rule with better branding?",
    "What would Diogenes say about influencers?",
    "Can money buy eudaimonia?",
    "What if everything I believe is wrong?",
  ];

  const pickRandom = useCallback(() => {
    return thoughtPrompts[Math.floor(Math.random() * thoughtPrompts.length)];
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q) {
      setError("Please enter a question for the council to debate");
      return;
    }
    if (q.length < 20) {
      setError("Question must be at least 20 characters so the council has enough to work with");
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      sessionStorage.setItem("agora-question", q);
      sessionStorage.setItem("agora-context", context.trim());
      navigate("/summon", {
        state: {
          question: q,
          context: context.trim(),
          documentIds: uploadedDocs.map((d) => d.id),
        },
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    const fileList = Array.from(files);
    // Reset input so same file can be re-selected
    e.target.value = "";

    for (const file of fileList) {
      setUploadingFiles((prev) => [...prev, file.name]);
      try {
        const doc = await uploadDocument(file);
        setUploadedDocs((prev) => [...prev, doc]);
      } catch (err) {
        setError(`Failed to upload ${file.name}: ${err instanceof Error ? err.message : "Unknown error"}`);
      } finally {
        setUploadingFiles((prev) => prev.filter((n) => n !== file.name));
      }
    }
  };

  const removeDoc = async (doc: UploadedDocument) => {
    setUploadedDocs((prev) => prev.filter((d) => d.id !== doc.id));
    try {
      await deleteDocument(doc.id);
    } catch {
      // best-effort delete
    }
  };

  const exampleQuestions = [
    { q: "Should I quit my job to travel the world for a year?", color: "#FF6B9D" },
    { q: "Is pineapple on pizza morally acceptable at all?", color: "#FFB86B" },
    { q: "What is the true meaning of a good life?", color: "#6B9DFF" },
    { q: "Should I adopt a cat or a dog as my companion?", color: "#8B6BFF" },
  ];

  const breathingAnimation = {
    animate: {
      y: [0, -8, 0],
      transition: { duration: 3, repeat: Infinity, ease: "easeInOut" },
    },
  };

  const hoverAnimation = {
    scale: 1.1,
    rotate: [0, -5, 5, 0],
    transition: { duration: 0.5 },
  };

  return (
    <div className="min-h-screen p-4 md:p-8 relative overflow-hidden">
      {/* Pixel art pediment — bottom-right */}
      <div
        className="pointer-events-none fixed right-0 select-none z-0"
        style={{ width: "30vw", maxWidth: "480px", bottom: "-20px", right: "-20px" }}
      >
        <img
          src="/pediment.png"
          alt=""
          className="w-full h-auto block"
          style={{ imageRendering: "pixelated" }}
        />
      </div>

      {/* Pixel art plant — bottom-left */}
      <div
        className="pointer-events-none fixed left-0 select-none z-0"
        style={{ width: "24vw", maxWidth: "360px", bottom: "-35px", left: "-45px" }}
      >
        <img
          src="/pixelart/plant.png"
          alt=""
          className="w-full h-auto block"
          style={{ imageRendering: "pixelated" }}
        />
      </div>

      {/* Desktop philosopher pets */}
      {pets.map((pet) => (
        <DesktopPet
          key={pet.character}
          character={pet.character}
          initialX={pet.x}
          initialDelay={pet.delay}
        />
      ))}
      <div className="max-w-4xl mx-auto relative z-[1]">
        {/* Header */}
        <div className="text-center mb-12 pt-2">
          <div className="relative inline-block mb-6">
            <div className="flex items-center justify-center mb-2">
              <div className="flex-1 h-[2px] bg-black"></div>
            </div>

            <div className="flex items-center justify-center gap-6 md:gap-12 px-4 md:px-8 py-4">
              {/* Left Bust */}
              <div
                className="relative hidden md:block"
                onMouseEnter={() => { setLeftPrompt(pickRandom()); setHoveredColumn("left"); }}
                onMouseLeave={() => setHoveredColumn(null)}
              >
                <motion.img
                  src={bustLeft}
                  alt="Greek bust"
                  className="w-20 h-24 md:w-32 md:h-40 object-contain cursor-pointer"
                  style={{ transformOrigin: "center bottom" }}
                  initial={{ scale: 1.1 }}
                  animate={{ scale: 1.1, y: [0, -8, 0] }}
                  transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                  whileHover={hoverAnimation}
                />
                {hoveredColumn === "left" && <ThoughtBubble text={leftPrompt} direction="left" />}
              </div>

              <div className="flex flex-col items-center">
                <div className="flex items-center justify-center gap-4 mb-3">
                  <GreekIllustration type="column" className="w-12 h-16 text-black" />
                  <h1 className="text-4xl md:text-6xl font-bold tracking-tight">THE AGORA</h1>
                  <GreekIllustration type="column" className="w-12 h-16 text-black" />
                </div>
                <BrutalistCard variant="secondary" className="inline-block px-6 py-3 mt-2">
                  <p className="text-lg">Summon anyone to debate anything.</p>
                </BrutalistCard>
              </div>

              {/* Right Bust */}
              <div
                className="relative hidden md:block"
                onMouseEnter={() => { setRightPrompt(pickRandom()); setHoveredColumn("right"); }}
                onMouseLeave={() => setHoveredColumn(null)}
              >
                <motion.img
                  src={bustRight}
                  alt="Greek bust"
                  className="w-20 h-24 md:w-32 md:h-40 object-contain cursor-pointer"
                  {...breathingAnimation}
                  whileHover={hoverAnimation}
                />
                {hoveredColumn === "right" && <ThoughtBubble text={rightPrompt} direction="right" />}
              </div>
            </div>
          </div>

          <p className="text-muted-foreground max-w-2xl mx-auto">
            Ask any question — trivial or serious — and watch a council of great minds deliberate.
            Get real multi-agent analysis with stance tracking and a synthesized verdict.
          </p>
        </div>

        {/* Main Question Input */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Question (2/3) */}
          <div className="lg:col-span-2">
            <BrutalistCard className="p-8 h-full">
              <form onSubmit={handleSubmit}>
                <label className="block mb-4">
                  <span className="flex items-center gap-2 mb-3">
                    <Sparkles className="w-5 h-5" />
                    What question shall the council decide on?
                  </span>
                  <textarea
                    value={question}
                    onChange={(e) => {
                      setQuestion(e.target.value);
                      if (error) setError("");
                    }}
                    placeholder="Type anything... the more specific, the better. (min 20 characters)"
                    className={`w-full p-4 border-[3px] ${error ? "border-red-500" : "border-black"} bg-white resize-none focus:outline-none focus:ring-4 ${error ? "focus:ring-red-500/20" : "focus:ring-black/20"}`}
                    rows={8}
                  />
                  {question.length > 0 && (
                    <p className={`text-xs mt-1 ${question.length < 20 ? "text-orange-500" : "text-muted-foreground"}`}>
                      {question.length} characters{question.length < 20 ? ` — need ${20 - question.length} more` : ""}
                    </p>
                  )}
                </label>

                {error && (
                  <div className="mb-4 p-3 bg-red-100 border-2 border-red-500 flex items-start gap-2">
                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                )}

                <div className="flex justify-end">
                  <BrutalistButton type="submit" variant="primary" size="sm" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Preparing...</>
                    ) : (
                      "Summon Council →"
                    )}
                  </BrutalistButton>
                </div>
              </form>
            </BrutalistCard>
          </div>

          {/* Context + Files (1/3) */}
          <div className="lg:col-span-1">
            <BrutalistCard className="p-6 h-full bg-[#F0EDE6]">
              <h3 className="mb-3 text-sm font-semibold">Additional Context</h3>
              <p className="text-xs text-muted-foreground mb-3">
                Provide background info to help the council understand your situation (optional)
              </p>
              <textarea
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="E.g., I'm 28 and secretly run a double life as a competitive cheese taster and part-time astrologer for dogs..."
                className="w-full p-3 border-2 border-black bg-white resize-none text-sm focus:outline-none focus:ring-4 focus:ring-black/20 mb-3"
                rows={5}
              />

              {/* File Upload */}
              <div className="mb-3">
                <label className="block cursor-pointer">
                  <input
                    type="file"
                    onChange={handleFileUpload}
                    className="hidden"
                    multiple
                    accept=".txt,.md,.pdf"
                  />
                  <div className="flex items-center justify-center gap-2 p-3 border-2 border-dashed border-black bg-white hover:bg-gray-50 transition-colors">
                    <Upload className="w-4 h-4" />
                    <span className="text-xs">Upload context files (.txt, .md, .pdf)</span>
                  </div>
                </label>
              </div>

              {/* Uploading indicator */}
              {uploadingFiles.map((name) => (
                <div key={name} className="flex items-center gap-2 p-2 bg-white border-2 border-black text-xs mb-1 opacity-60">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span className="truncate">{name}</span>
                </div>
              ))}

              {/* Uploaded files */}
              {uploadedDocs.length > 0 && (
                <div className="space-y-2">
                  {uploadedDocs.map((doc) => (
                    <div key={doc.id} className="flex items-center justify-between p-2 bg-white border-2 border-black text-xs">
                      <div className="truncate flex-1 mr-2">
                        <span>{doc.filename}</span>
                        {doc.extraction_status === "failed" && (
                          <span className="text-red-500 ml-1">(extract failed)</span>
                        )}
                      </div>
                      <button
                        onClick={() => removeDoc(doc)}
                        className="flex-shrink-0 w-5 h-5 flex items-center justify-center bg-black text-white hover:bg-red-500 transition-colors"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </BrutalistCard>
          </div>
        </div>

        {/* Example Questions */}
        <div className="mb-48">
          <h3 className="mb-4">Or try one of these:</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {exampleQuestions.map((item, i) => (
              <BrutalistCard
                key={i}
                hoverable
                className="p-4 cursor-pointer transition-all"
                onClick={() => setQuestion(item.q)}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = item.color)}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "")}
              >
                <p className="text-sm">{item.q}</p>
              </BrutalistCard>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}

function ThoughtBubble({ text, direction }: { text: string; direction: "left" | "right" }) {
  return (
    <div
      className={`absolute top-1/2 -translate-y-1/2 pointer-events-none z-50 flex items-center ${
        direction === "left" ? "right-full mr-1 flex-row-reverse" : "left-full ml-1 flex-row"
      }`}
    >
      <div className={`flex items-center gap-[3px] ${direction === "left" ? "flex-row" : "flex-row-reverse"}`}>
        <div className="w-[4px] h-[4px] rounded-full bg-white border border-black" />
        <div className="w-[6px] h-[6px] rounded-full bg-white border-[1.5px] border-black" />
        <div className="w-[8px] h-[8px] rounded-full bg-white border-2 border-black" />
      </div>
      <div
        className="bg-white border-[2px] border-black shadow-[2px_2px_0_0_#0A0A0A] rounded-xl px-2 py-1.5 leading-snug"
        style={{ width: "120px", fontSize: "10px" }}
      >
        {text}
      </div>
    </div>
  );
}
