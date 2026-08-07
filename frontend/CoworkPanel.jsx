import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Bot,
  Check,
  ChevronRight,
  CircleDot,
  Copy,
  FileCode2,
  FolderOpen,
  GitBranch,
  HardDrive,
  History,
  MessageSquareText,
  MoreHorizontal,
  Plus,
  RefreshCw,
  SendHorizonal,
  ShieldCheck,
  SquareTerminal,
  UserRound,
  X,
} from "lucide-react";
import { buildCoworkPrompt, buildCoworkTranscript, createCoworkMessage, normalizeCoworkRole } from "./coworkUtils";
import { answerQuestion, eelEvents, hasEel, selectFolder, sendCowork, subscribeEelEvent } from "./lib/eel";

const COWORK_MESSAGES_STORAGE_KEY = "api-blender.cowork.messages.v1";

function MessageBlock({ message }) {
  if (message.role === "system") {
    return (
      <div className="fade-up flex gap-3 py-3">
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-line bg-[#111214] text-dim">
          <SquareTerminal size={12} />
        </div>
        <div className="min-w-0 flex-1 rounded-lg border border-line bg-[#111214] px-3.5 py-3 font-mono text-[11px] leading-5 text-muted">
          <div className="mb-1.5 flex items-center gap-2 text-[9px] uppercase tracking-[0.18em] text-dim">
            System event <span className="text-line2">/</span> {message.time}
          </div>
          <div className="whitespace-pre-wrap break-words">{message.text}</div>
        </div>
      </div>
    );
  }

  const isUser = message.role === "user";

  return (
    <article className="fade-up group flex gap-3 border-b border-line/60 py-5 last:border-b-0">
      <div
        className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border ${
          isUser ? "border-line bg-panel2 text-muted" : "border-emerald-400/25 bg-emerald-400/10 text-emerald-300"
        }`}
      >
        {isUser ? <UserRound size={13} /> : <Bot size={14} />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-xs font-semibold text-ink">{isUser ? "You" : "Cowork"}</span>
          <span className="font-mono text-[10px] text-dim">{message.time}</span>
          {!isUser && message.modelLabel && (
            <span className="truncate rounded-md border border-line bg-panel2 px-1.5 py-0.5 font-mono text-[9px] text-muted">
              {message.modelLabel}
            </span>
          )}
        </div>
        <div className="whitespace-pre-wrap break-words text-[13px] leading-6 text-[#d8dadd]">{message.text}</div>
      </div>
    </article>
  );
}

function RailButton({ icon: Icon, label, active = false, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs transition-colors ${
        active ? "bg-[#25272b] text-ink" : "text-muted hover:bg-[#1d1f22] hover:text-ink"
      }`}
    >
      <Icon size={14} />
      <span className="min-w-0 flex-1 truncate">{label}</span>
    </button>
  );
}

function InspectorRow({ icon: Icon, label, value, tone = "text-muted" }) {
  return (
    <div className="flex items-start gap-2.5 py-2.5">
      <Icon size={13} className={`mt-0.5 shrink-0 ${tone}`} />
      <div className="min-w-0 flex-1">
        <div className="text-[10px] uppercase tracking-[0.13em] text-dim">{label}</div>
        <div className="mt-0.5 truncate text-[11px] text-muted" title={value}>{value}</div>
      </div>
    </div>
  );
}

export default function Cowork({
  bridgeState,
  coworkModel,
  coworkModelLabel,
  isActive,
  coworkMessages,
  setCoworkMessages,
  coworkUiState,
  setCoworkUiState,
}) {
  const [input, setInput] = useState("");
  const [workingDirectory, setWorkingDirectory] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState(null);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [historyHydrated, setHistoryHydrated] = useState(false);
  const pendingAssistantModelRef = useRef(coworkModelLabel);
  const pendingUserEchoRef = useRef(null);
  const scrollRef = useRef(null);
  const isBusy = coworkUiState === "busy";
  const tokenEstimate = coworkMessages.length === 0 ? 0 : Math.round(JSON.stringify(coworkMessages).length / 4);
  const workspaceLabel = workingDirectory ? workingDirectory.split(/[\\/]/).filter(Boolean).at(-1) : "No project selected";

  useEffect(() => {
    try {
      const savedMessages = window.localStorage.getItem(COWORK_MESSAGES_STORAGE_KEY);
      if (coworkMessages.length === 0 && savedMessages) {
        const parsedMessages = JSON.parse(savedMessages);
        if (Array.isArray(parsedMessages)) {
          setCoworkMessages(parsedMessages.slice(-200));
        }
      }
    } catch (error) {
      console.warn("Could not restore Cowork conversation history.", error);
    } finally {
      setHistoryHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!historyHydrated) return;
    try {
      window.localStorage.setItem(COWORK_MESSAGES_STORAGE_KEY, JSON.stringify(coworkMessages.slice(-200)));
    } catch (error) {
      console.warn("Could not persist Cowork conversation history.", error);
    }
  }, [coworkMessages, historyHydrated]);

  useEffect(() => {
    const disposeLog = subscribeEelEvent(eelEvents.coworkLog, (event) => {
      const timestamp = event.detail?.timestamp ?? new Date().toISOString();
      const role = normalizeCoworkRole(event.detail?.role);

      if (role === "user") {
        const echoedPrompt = String(event.detail?.text ?? "").trim();
        if (pendingUserEchoRef.current && echoedPrompt === pendingUserEchoRef.current) {
          pendingUserEchoRef.current = null;
          return;
        }
      }

      const modelLabel = role === "ai" ? pendingAssistantModelRef.current ?? coworkModelLabel : undefined;
      setCoworkMessages((current) => [
        ...current,
        createCoworkMessage(role, event.detail?.text ?? "", timestamp, modelLabel),
      ]);
    });

    const disposeUiState = subscribeEelEvent(eelEvents.coworkUiState, (event) => {
      const nextState = event.detail?.state === "busy" ? "busy" : "idle";
      setCoworkUiState(nextState);
      if (nextState !== "busy") {
        pendingAssistantModelRef.current = null;
        pendingUserEchoRef.current = null;
      }
    });

    const disposeQuestion = subscribeEelEvent(eelEvents.coworkInteractiveQuestion, (event) => {
      const question = typeof event.detail?.question === "string" ? event.detail.question : "";
      const options = Array.isArray(event.detail?.options) ? event.detail.options.map(String) : [];
      if (question && options.length > 0) {
        setPendingQuestion({ question, options });
      }
    });

    return () => {
      disposeLog();
      disposeUiState();
      disposeQuestion();
    };
  }, [coworkModelLabel, setCoworkMessages, setCoworkUiState]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [coworkMessages, isActive, isBusy]);

  const resetConversation = () => {
    setCoworkMessages([]);
    setCoworkUiState("idle");
    window.localStorage.removeItem(COWORK_MESSAGES_STORAGE_KEY);
  };

  const exportConversation = async () => {
    const transcript = coworkMessages.length > 0 ? buildCoworkTranscript(coworkMessages) : "";
    if (transcript) {
      await navigator.clipboard?.writeText(transcript);
    }
  };

  const pickWorkingDirectory = async () => {
    if (!hasEel()) return;
    try {
      const selectedDirectory = await selectFolder();
      if (typeof selectedDirectory === "string" && selectedDirectory.trim()) {
        setWorkingDirectory(selectedDirectory.trim());
      }
    } catch (error) {
      console.error("Failed to select working directory.", error);
    }
  };

  const handleAnswer = async (choice) => {
    setPendingQuestion(null);
    await answerQuestion(choice);
  };

  const send = async () => {
    const prompt = input.trim();
    if (!prompt || isBusy) return;

    const promptWithContext = buildCoworkPrompt(prompt, workingDirectory);
    const timestamp = new Date().toISOString();
    setInput("");
    setCoworkMessages((current) => [...current, createCoworkMessage("user", prompt, timestamp)]);

    if (!hasEel()) {
      setCoworkMessages((current) => [
        ...current,
        createCoworkMessage("ai", "Desktop bridge unavailable. Launch the Electron shell to reach the Python sidecar.", timestamp, coworkModelLabel),
      ]);
      setCoworkUiState("idle");
      return;
    }

    pendingAssistantModelRef.current = coworkModelLabel;
    pendingUserEchoRef.current = promptWithContext.trim();
    setCoworkUiState("busy");

    try {
      await sendCowork(promptWithContext, coworkModel);
    } catch (error) {
      pendingAssistantModelRef.current = null;
      pendingUserEchoRef.current = null;
      setCoworkUiState("idle");
      setCoworkMessages((current) => [
        ...current,
        createCoworkMessage("system", `Cowork dispatch failed: ${error instanceof Error ? error.message : String(error)}`),
      ]);
    }
  };

  return (
    <div className="flex h-full min-h-[620px] overflow-hidden rounded-[18px] border border-line bg-[#101113] shadow-panel">
      <aside className="hidden w-[190px] shrink-0 flex-col border-r border-line bg-[#151619] lg:flex">
        <div className="border-b border-line px-3 py-3">
          <button
            type="button"
            onClick={resetConversation}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-line bg-[#1d1f22] px-3 py-2 text-xs font-medium text-ink transition-colors hover:border-line2"
          >
            <Plus size={14} /> New task
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-3">
          <div className="px-2 pb-1.5 font-mono text-[9px] uppercase tracking-[0.18em] text-dim">Workspace</div>
          <RailButton icon={MessageSquareText} label="Current session" active />
          <RailButton icon={History} label="Recent tasks" />
          <RailButton icon={FileCode2} label="Changed files" />

          <div className="mt-5 px-2 pb-1.5 font-mono text-[9px] uppercase tracking-[0.18em] text-dim">Project</div>
          <button
            type="button"
            onClick={pickWorkingDirectory}
            disabled={!hasEel()}
            className="w-full rounded-lg border border-dashed border-line px-2.5 py-3 text-left transition-colors hover:border-line2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <div className="flex items-center gap-2 text-xs text-muted">
              <FolderOpen size={14} className="text-blender" />
              <span className="truncate">{workspaceLabel}</span>
            </div>
            <div className="mt-1.5 truncate pl-[22px] font-mono text-[9px] text-dim">
              {workingDirectory || "Choose repository"}
            </div>
          </button>
        </div>

        <div className="border-t border-line p-3">
          <div className="flex items-center gap-2 text-[10px] text-muted">
            <span className={`h-1.5 w-1.5 rounded-full ${bridgeState === "connected" ? "bg-emerald-400" : "bg-amber-400"}`} />
            {bridgeState === "dev" ? "Preview mode" : "Python bridge online"}
          </div>
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[54px] shrink-0 items-center gap-3 border-b border-line px-4 sm:px-5">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-300">
              <SquareTerminal size={14} />
            </div>
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold text-ink">{workspaceLabel}</div>
              <div className="flex items-center gap-1.5 font-mono text-[9px] text-dim">
                <GitBranch size={9} /> local workspace <ChevronRight size={9} /> cowork
              </div>
            </div>
          </div>
          <span className={`hidden items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[9px] sm:flex ${
            isBusy ? "border-amber-400/30 bg-amber-400/10 text-amber-300" : "border-emerald-400/25 bg-emerald-400/10 text-emerald-300"
          }`}>
            <CircleDot size={9} /> {isBusy ? "working" : "ready"}
          </span>
          <button type="button" onClick={exportConversation} className="rounded-md p-1.5 text-dim hover:bg-panel2 hover:text-ink" title="Copy transcript">
            <Copy size={14} />
          </button>
          <button type="button" onClick={() => setInspectorOpen((current) => !current)} className="rounded-md p-1.5 text-dim hover:bg-panel2 hover:text-ink" title="Toggle inspector">
            <Activity size={14} />
          </button>
          <button type="button" className="rounded-md p-1.5 text-dim hover:bg-panel2 hover:text-ink" title="More options">
            <MoreHorizontal size={15} />
          </button>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[760px] px-5 py-5 sm:px-8">
            {coworkMessages.length === 0 ? (
              <div className="fade-up flex min-h-[380px] flex-col justify-center">
                <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-400/20 bg-emerald-400/10 text-emerald-300">
                  <Bot size={19} />
                </div>
                <h2 className="max-w-xl text-2xl font-semibold tracking-[-0.03em] text-ink">What should we build?</h2>
                <p className="mt-2 max-w-xl text-[13px] leading-6 text-muted">
                  Cowork can inspect this repository, explain architecture, plan changes, and use local tools. Changes that affect files will move through the approval workflow as that capability is enabled.
                </p>
                <div className="mt-6 grid max-w-2xl gap-2 sm:grid-cols-2">
                  {[
                    [FileCode2, "Map this codebase", "Find entry points and explain the architecture"],
                    [ShieldCheck, "Review the safety boundary", "Audit file access and permission risks"],
                    [SquareTerminal, "Plan the next sprint", "Turn the roadmap into executable tasks"],
                    [Activity, "Test Local AI", "Verify model, tools, and response quality"],
                  ].map(([Icon, title, description]) => (
                    <button
                      key={title}
                      type="button"
                      onClick={() => setInput(description)}
                      className="group rounded-xl border border-line bg-[#151619] p-3.5 text-left transition-colors hover:border-line2 hover:bg-[#191b1e]"
                    >
                      <Icon size={14} className="text-dim transition-colors group-hover:text-blender" />
                      <div className="mt-2 text-xs font-medium text-ink">{title}</div>
                      <div className="mt-1 text-[10px] leading-4 text-dim">{description}</div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              coworkMessages.map((message, index) => <MessageBlock key={`${message.timestamp}-${index}`} message={message} />)
            )}

            {isBusy && (
              <div className="fade-up flex gap-3 border-t border-line/60 py-5">
                <div className="spin-slow flex h-7 w-7 items-center justify-center rounded-lg border border-emerald-400/25 bg-emerald-400/10 text-emerald-300">
                  <RefreshCw size={13} />
                </div>
                <div>
                  <div className="text-xs font-medium text-ink">Cowork is inspecting the project</div>
                  <div className="mt-1 font-mono text-[10px] text-dim">reasoning / selecting context / preparing tools</div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 px-4 pb-4 sm:px-6">
          <div className="mx-auto max-w-[760px]">
            {pendingQuestion && (
              <div className="fade-up mb-2 rounded-xl border border-amber-400/30 bg-amber-400/8 p-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-xs font-medium text-ink">{pendingQuestion.question}</p>
                  <button type="button" onClick={() => setPendingQuestion(null)} className="text-dim hover:text-ink"><X size={13} /></button>
                </div>
                <div className="mt-2.5 flex flex-wrap gap-2">
                  {pendingQuestion.options.map((option, index) => (
                    <button key={`${option}-${index}`} type="button" onClick={() => void handleAnswer(option)} className="rounded-md border border-line2 bg-panel2 px-2.5 py-1.5 text-[10px] text-ink hover:border-blender/50">
                      {option}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="overflow-hidden rounded-xl border border-line2 bg-[#191a1d] shadow-[0_12px_40px_rgba(0,0,0,0.28)] transition-colors focus-within:border-[#4a4d53]">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.preventDefault();
                    void send();
                  }
                }}
                placeholder="Ask Cowork to inspect, plan, or change the project..."
                rows="3"
                disabled={isBusy}
                className="w-full resize-none bg-transparent px-4 pb-2 pt-3.5 text-[13px] leading-5 text-ink placeholder:text-dim focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
              />
              <div className="flex items-center justify-between border-t border-line px-2.5 py-2">
                <div className="flex min-w-0 items-center gap-1.5">
                  <button type="button" onClick={pickWorkingDirectory} disabled={!hasEel()} className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[10px] text-muted hover:bg-[#232529] hover:text-ink disabled:opacity-40">
                    <FolderOpen size={12} /> <span className="hidden sm:inline">{workspaceLabel}</span>
                  </button>
                  <span className="hidden rounded-md bg-[#111214] px-2 py-1 font-mono text-[9px] text-dim md:inline">~{tokenEstimate} tokens</span>
                  <span className="hidden max-w-[190px] truncate rounded-md bg-[#111214] px-2 py-1 font-mono text-[9px] text-dim xl:inline">{coworkModelLabel}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="hidden font-mono text-[9px] text-dim sm:inline">Ctrl + Enter</span>
                  <button
                    type="button"
                    onClick={send}
                    disabled={!input.trim() || isBusy}
                    className="flex h-7 items-center gap-1.5 rounded-md bg-[#e8e8e8] px-3 text-[10px] font-semibold text-[#151515] transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-30"
                  >
                    <SendHorizonal size={11} /> {isBusy ? "Running" : "Send"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {inspectorOpen && (
        <aside className="hidden w-[210px] shrink-0 flex-col border-l border-line bg-[#151619] xl:flex">
          <div className="flex h-[54px] items-center justify-between border-b border-line px-3.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Run context</span>
            <button type="button" onClick={() => setInspectorOpen(false)} className="text-dim hover:text-ink"><X size={13} /></button>
          </div>
          <div className="flex-1 overflow-y-auto px-3.5 py-3">
            <InspectorRow icon={HardDrive} label="Provider" value="LM Studio / local" tone="text-emerald-300" />
            <InspectorRow icon={Bot} label="Model" value={coworkModelLabel} />
            <InspectorRow icon={FolderOpen} label="Working directory" value={workingDirectory || "Not selected"} />
            <InspectorRow icon={MessageSquareText} label="Conversation" value={`${coworkMessages.length} messages / ~${tokenEstimate} tokens`} />

            <div className="my-3 border-t border-line" />
            <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-dim">Capabilities</div>
            <div className="mt-2 space-y-1.5">
              {["Read project files", "Search source code", "Local tool calling", "Project memory"].map((label) => (
                <div key={label} className="flex items-center gap-2 text-[10px] text-muted">
                  <Check size={11} className="text-emerald-300" /> {label}
                </div>
              ))}
            </div>

            <div className="my-3 border-t border-line" />
            <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-dim">Coming next</div>
            <div className="mt-2 space-y-1.5 text-[10px] leading-4 text-dim">
              <div>Permission approval</div>
              <div>Diff preview</div>
              <div>Test and lint results</div>
              <div>Git change timeline</div>
            </div>
          </div>
        </aside>
      )}
    </div>
  );
}
