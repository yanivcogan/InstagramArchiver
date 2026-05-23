"""Subprocess entry for the 'Finish Archiving' floating button.

This MUST run as its own process, never as a thread inside archive.py. Tk's
Tcl interpreter has thread affinity: if Tk objects created on one thread are
finalized (by Python GC) on another thread, Tcl calls Tcl_Panic and aborts
the entire process — losing the archive. Running in a subprocess means our
process never touches this Tk interpreter, so the bug can't hit us.

Process lifecycle is the signal: the subprocess exits when the user clicks
'Finish Archiving' OR closes the window. archive.py polls `proc.poll()`.
"""
import sys
import tkinter as tk


def main() -> None:
    try:
        root = tk.Tk()
    except Exception as e:
        # Window failed to start — exit so the parent doesn't wait on us.
        # archive.py will fall back to X-button-only close (less reliable
        # but still works ~95% of the time).
        print(f"Finish-button window failed to start: {e}", file=sys.stderr)
        sys.exit(2)

    root.title("Archiver")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    win_w, win_h = 240, 110
    screen_w = root.winfo_screenwidth()
    # Top-right of the primary monitor. The screen recorder only captures
    # the Firefox window region (see archive.screen_record), so anything
    # outside that rectangle is not in the recording.
    root.geometry(f"{win_w}x{win_h}+{screen_w - win_w - 20}+20")

    tk.Label(
        root,
        text="Click when done navigating.\nSafely flushes the HAR before close.",
        font=("Arial", 9),
        justify="center",
    ).pack(pady=(8, 4))

    def on_finish():
        root.destroy()

    tk.Button(root, text="Finish Archiving", command=on_finish, height=2).pack(
        fill="both", expand=True, padx=10, pady=(0, 8)
    )
    # X button is also 'Finish' — better than silently dismissing it.
    root.protocol("WM_DELETE_WINDOW", on_finish)

    root.mainloop()
    sys.exit(0)


if __name__ == "__main__":
    main()
