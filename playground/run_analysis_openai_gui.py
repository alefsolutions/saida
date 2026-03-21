from __future__ import annotations

from pathlib import Path
import json
import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from _env import load_project_env
from saida import Saida
from saida.config import LlmConfig, SaidaConfig
from saida.core import AnalysisResult, Dataset
from saida.sources import CSVSource


class OpenAiPlaygroundApp:
    """Simple modern chat-style UI for the SAIDA OpenAI playground."""

    EXIT_WORDS = {"exit", "quit", "q"}
    BG = "#f6f3ec"
    PANEL_BG = "#fbf9f4"
    PANEL_BORDER = "#ddd6c8"
    HEADER_TEXT = "#182522"
    SUBTLE_TEXT = "#64716d"
    USER_BG = "#18322d"
    USER_TEXT = "#f4f7f4"
    ASSISTANT_BG = "#fffdf8"
    ASSISTANT_TEXT = "#1d2c29"
    INPUT_BG = "#ffffff"
    INPUT_BORDER = "#d7d2c7"
    ACCENT_BG = "#e7f2ee"
    ACCENT_TEXT = "#0d6d53"
    LOADER_BG = "#e5ebfb"
    LOADER_TEXT = "#2940a8"
    WARN_BG = "#f5e6d4"
    WARN_TEXT = "#8a4f00"
    ERROR_BG = "#f6dfdd"
    ERROR_TEXT = "#9b2f22"

    def __init__(self) -> None:
        load_project_env(PROJECT_ROOT)
        self._validate_environment()

        self.dataset = self._load_dataset()
        self.engine = self._build_engine()
        self.pending_clarification = False
        self.loader_job: str | None = None
        self.loader_frame_index = 0

        self.root = tk.Tk()
        self.root.title("SAIDA OpenAI Playground")
        self.root.geometry("1320x780")
        self.root.minsize(1080, 680)
        self.root.configure(bg=self.BG)

        self.font_family = self._pick_font_family()
        self._build_ui()
        self._add_assistant_message(
            "SAIDA is ready.\nAsk a question about the sample sales dataset.",
            meta="OpenAI prompting and reasoning enabled",
        )
        self._set_contract_view(
            {
                "status": "ready",
                "message": "Structured response output will appear here after the first analysis.",
            }
        )

    def run(self) -> None:
        self.root.mainloop()

    def _validate_environment(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set.")

    def _load_dataset(self) -> Dataset:
        return CSVSource(
            PROJECT_ROOT / "examples" / "sales.csv",
            context_path=PROJECT_ROOT / "examples" / "sales_context.md",
        ).load()

    def _build_engine(self) -> Saida:
        config = SaidaConfig(
            llm=LlmConfig(
                enabled=True,
                provider="openai",
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                use_for_prompting=True,
                use_for_reasoning=True,
            )
        )
        return Saida(config=config)

    def _pick_font_family(self) -> str:
        families = set(tkfont.families())
        if "Rubik" in families:
            return "Rubik"
        return "Segoe UI"

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        header = tk.Frame(self.root, bg=self.BG, padx=28, pady=20)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = tk.Label(
            header,
            text="SAIDA OpenAI Playground",
            font=(self.font_family, 24, "bold"),
            fg=self.HEADER_TEXT,
            bg=self.BG,
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = tk.Label(
            header,
            text="Modern chat UI for testing prompts, deterministic analytics, and optional LLM reasoning.",
            font=(self.font_family, 11),
            fg=self.SUBTLE_TEXT,
            bg=self.BG,
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.status_label = tk.Label(
            header,
            text="Ready",
            font=(self.font_family, 10, "bold"),
            fg=self.ACCENT_TEXT,
            bg=self.ACCENT_BG,
            padx=12,
            pady=6,
        )
        self.status_label.grid(row=0, column=1, rowspan=2, sticky="e")

        body = tk.Frame(self.root, bg=self.BG, padx=24, pady=6)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)

        chat_shell = tk.Frame(
            body,
            bg=self.PANEL_BG,
            highlightthickness=1,
            highlightbackground=self.PANEL_BORDER,
        )
        chat_shell.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        chat_shell.grid_rowconfigure(0, weight=1)
        chat_shell.grid_columnconfigure(0, weight=1)

        chat_header = tk.Frame(chat_shell, bg="#f2ede1", padx=18, pady=14)
        chat_header.grid(row=0, column=0, columnspan=2, sticky="ew")

        chat_title = tk.Label(
            chat_header,
            text="Conversation",
            font=(self.font_family, 13, "bold"),
            fg=self.HEADER_TEXT,
            bg="#f2ede1",
        )
        chat_title.pack(anchor="w")

        chat_hint = tk.Label(
            chat_header,
            text="Ask about the sample sales dataset. Responses prefer the LLM summary when available.",
            font=(self.font_family, 9),
            fg=self.SUBTLE_TEXT,
            bg="#f2ede1",
        )
        chat_hint.pack(anchor="w", pady=(2, 0))

        self.chat_canvas = tk.Canvas(
            chat_shell,
            bg=self.PANEL_BG,
            highlightthickness=0,
            bd=0,
        )
        self.chat_canvas.grid(row=1, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(chat_shell, orient="vertical", command=self.chat_canvas.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.chat_canvas.configure(yscrollcommand=scrollbar.set)

        self.chat_frame = tk.Frame(self.chat_canvas, bg=self.PANEL_BG)
        self.chat_window = self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")

        self.chat_frame.bind("<Configure>", self._on_chat_frame_configure)
        self.chat_canvas.bind("<Configure>", self._on_chat_canvas_configure)

        inspector = tk.Frame(
            body,
            bg=self.PANEL_BG,
            highlightthickness=1,
            highlightbackground=self.PANEL_BORDER,
        )
        inspector.grid(row=0, column=1, sticky="nsew")
        inspector.grid_rowconfigure(1, weight=1)
        inspector.grid_columnconfigure(0, weight=1)

        inspector_header = tk.Frame(inspector, bg="#f2ede1", padx=16, pady=14)
        inspector_header.grid(row=0, column=0, sticky="ew")

        inspector_title = tk.Label(
            inspector_header,
            text="Response Contract",
            font=(self.font_family, 13, "bold"),
            fg=self.HEADER_TEXT,
            bg="#f2ede1",
        )
        inspector_title.pack(anchor="w")

        inspector_subtitle = tk.Label(
            inspector_header,
            text="Latest result.to_response_dict() output",
            font=(self.font_family, 9),
            fg=self.SUBTLE_TEXT,
            bg="#f2ede1",
        )
        inspector_subtitle.pack(anchor="w", pady=(2, 0))

        self.contract_view = tk.Text(
            inspector,
            wrap="word",
            bd=0,
            highlightthickness=0,
            font=("Consolas", 10),
            fg=self.ASSISTANT_TEXT,
            bg=self.PANEL_BG,
            padx=16,
            pady=16,
            state="disabled",
            insertbackground=self.ASSISTANT_TEXT,
        )
        self.contract_view.grid(row=1, column=0, sticky="nsew")

        composer = tk.Frame(self.root, bg=self.BG, padx=24, pady=18)
        composer.grid(row=2, column=0, sticky="ew")
        composer.grid_columnconfigure(0, weight=1)

        input_shell = tk.Frame(
            composer,
            bg=self.INPUT_BG,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.INPUT_BORDER,
        )
        input_shell.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        input_shell.grid_columnconfigure(0, weight=1)

        self.input_box = tk.Text(
            input_shell,
            height=3,
            wrap="word",
            bd=0,
            highlightthickness=0,
            font=(self.font_family, 12),
            fg=self.ASSISTANT_TEXT,
            bg=self.INPUT_BG,
            padx=16,
            pady=14,
            insertbackground=self.ASSISTANT_TEXT,
        )
        self.input_box.grid(row=0, column=0, sticky="ew")
        self.input_box.bind("<Return>", self._handle_enter_key)
        self.input_box.bind("<Shift-Return>", self._allow_newline)
        self.input_box.focus_set()

        send_button = tk.Button(
            composer,
            text="Send",
            command=self._submit_prompt,
            font=(self.font_family, 11, "bold"),
            fg="#ffffff",
            bg=self.USER_BG,
            activeforeground="#ffffff",
            activebackground="#102925",
            relief="flat",
            padx=22,
            pady=14,
            cursor="hand2",
        )
        send_button.grid(row=0, column=1, sticky="se")

    def _on_chat_frame_configure(self, event: tk.Event[tk.Widget]) -> None:
        _ = event
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(1.0)

    def _on_chat_canvas_configure(self, event: tk.Event[tk.Widget]) -> None:
        self.chat_canvas.itemconfigure(self.chat_window, width=event.width)

    def _handle_enter_key(self, event: tk.Event[tk.Widget]) -> str | None:
        if event.state & 0x0001:
            return None
        self._submit_prompt()
        return "break"

    def _allow_newline(self, event: tk.Event[tk.Widget]) -> None:
        _ = event

    def _submit_prompt(self) -> None:
        question = self.input_box.get("1.0", "end").strip()
        if not question:
            return
        if question.lower() in self.EXIT_WORDS:
            self.root.destroy()
            return

        self.input_box.delete("1.0", "end")
        self._set_busy_state(True)

        if self.pending_clarification:
            self.pending_clarification = False

        self._add_user_message(question)
        worker = threading.Thread(target=self._run_analysis, args=(question,), daemon=True)
        worker.start()

    def _run_analysis(self, question: str) -> None:
        try:
            result = self.engine.analyze(self.dataset, question)
        except Exception as exc:  # pragma: no cover
            self.root.after(0, self._handle_error, str(exc))
            return
        self.root.after(0, self._handle_result, result)

    def _handle_result(self, result: AnalysisResult) -> None:
        meta_parts = [f"Summary source: {result.summary_source}"]
        if result.tables:
            meta_parts.append("Tables: " + ", ".join(table.name for table in result.tables))
        if result.warnings:
            meta_parts.append("Warnings: " + "; ".join(result.warnings))

        display_text = result.llm_summary or result.summary
        self._add_assistant_message(display_text, meta=" | ".join(meta_parts))
        self._set_contract_view(result.to_response_dict())

        if result.plan.task_type == "clarification":
            self.pending_clarification = True
            self.status_label.configure(text="Clarification needed", bg=self.WARN_BG, fg=self.WARN_TEXT)
        else:
            self.status_label.configure(text="Ready", bg=self.ACCENT_BG, fg=self.ACCENT_TEXT)

        self._set_busy_state(False)

    def _handle_error(self, message: str) -> None:
        self._set_busy_state(False)
        self.status_label.configure(text="Error", bg=self.ERROR_BG, fg=self.ERROR_TEXT)
        self._set_contract_view({"status": "error", "message": message})
        messagebox.showerror("SAIDA Playground Error", message)

    def _set_busy_state(self, busy: bool) -> None:
        if busy:
            self.input_box.configure(state="disabled")
            self._start_loader()
        else:
            self.input_box.configure(state="normal")
            self._stop_loader()
            self.input_box.focus_set()

    def _start_loader(self) -> None:
        self.loader_frame_index = 0
        self._animate_loader()

    def _animate_loader(self) -> None:
        frames = [".", "..", "..."]
        self.status_label.configure(
            text=f"Thinking{frames[self.loader_frame_index % len(frames)]}",
            bg=self.LOADER_BG,
            fg=self.LOADER_TEXT,
        )
        self.loader_frame_index += 1
        self.loader_job = self.root.after(420, self._animate_loader)

    def _stop_loader(self) -> None:
        if self.loader_job is not None:
            self.root.after_cancel(self.loader_job)
            self.loader_job = None

    def _add_user_message(self, text: str) -> None:
        self._add_message_bubble(text=text, is_user=True, meta=None)

    def _add_assistant_message(self, text: str, meta: str | None) -> None:
        self._add_message_bubble(text=text, is_user=False, meta=meta)

    def _add_message_bubble(self, text: str, is_user: bool, meta: str | None) -> None:
        outer = tk.Frame(self.chat_frame, bg=self.PANEL_BG, pady=8)
        outer.pack(fill="x", anchor="e" if is_user else "w")

        bubble = tk.Frame(
            outer,
            bg=self.USER_BG if is_user else self.ASSISTANT_BG,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.USER_BG if is_user else self.PANEL_BORDER,
            padx=18,
            pady=12,
        )
        bubble.pack(anchor="e" if is_user else "w", padx=(140, 14) if is_user else (14, 140))

        role_label = tk.Label(
            bubble,
            text="You" if is_user else "SAIDA",
            font=(self.font_family, 10, "bold"),
            fg="#dbe9e4" if is_user else self.SUBTLE_TEXT,
            bg=self.USER_BG if is_user else self.ASSISTANT_BG,
        )
        role_label.pack(anchor="w")

        text_label = tk.Label(
            bubble,
            text=text,
            justify="left",
            wraplength=560,
            font=(self.font_family, 12),
            fg=self.USER_TEXT if is_user else self.ASSISTANT_TEXT,
            bg=self.USER_BG if is_user else self.ASSISTANT_BG,
            pady=6,
        )
        text_label.pack(anchor="w")

        if meta:
            meta_label = tk.Label(
                bubble,
                text=meta,
                justify="left",
                wraplength=560,
                font=(self.font_family, 9),
                fg="#b9cbc5" if is_user else self.SUBTLE_TEXT,
                bg=self.USER_BG if is_user else self.ASSISTANT_BG,
            )
            meta_label.pack(anchor="w")

    def _set_contract_view(self, payload: dict[str, object]) -> None:
        formatted = json.dumps(payload, indent=2, ensure_ascii=True)
        self.contract_view.configure(state="normal")
        self.contract_view.delete("1.0", "end")
        self.contract_view.insert("1.0", formatted)
        self.contract_view.configure(state="disabled")


def main() -> None:
    app = OpenAiPlaygroundApp()
    app.run()


if __name__ == "__main__":
    main()
