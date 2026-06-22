import threading
import subprocess
import sys
import codecs
from collections import deque

class StreamAccumulator:
    """
    Bounds memory usage by keeping only the very first and very last chunks of output.
    Thread-safe to allow interleaving stdout and stderr chronologically.
    """
    def __init__(self, max_head_chunks=50, max_tail_chunks=200):
        self.head = []
        self.tail = deque(maxlen=max_tail_chunks)
        self.max_head = max_head_chunks
        self.chunks_seen = 0
        self.lock = threading.Lock()

    def append(self, text: str):
        with self.lock:
            if self.chunks_seen < self.max_head:
                self.head.append(text)
            else:
                self.tail.append(text)
            self.chunks_seen += 1

    def get_content(self) -> str:
        with self.lock:
            if self.chunks_seen <= self.max_head:
                return "".join(self.head)
            return "".join(self.head) + "\n... [ middle chunks omitted from memory to prevent OOM ] ...\n" + "".join(self.tail)

def stream_pipe(pipe, accumulator, terminal_stream, file_stream=None, file_lock=None):
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    while True:
        chunk = pipe.read(4096)
        if not chunk:
            if isinstance(chunk, bytes):
                text = decoder.decode(b"", final=True)
            else:
                text = ""
            if text:
                if terminal_stream:
                    print(text, end="", file=terminal_stream, flush=True)
                if file_stream:
                    if file_lock:
                        with file_lock:
                            print(text, end="", file=file_stream, flush=True)
                    else:
                        print(text, end="", file=file_stream, flush=True)
                accumulator.append(text)
            break

        if isinstance(chunk, bytes):
            text = decoder.decode(chunk)
        else:
            text = chunk
        if text:
            if terminal_stream:
                print(text, end="", file=terminal_stream, flush=True)
            if file_stream:
                if file_lock:
                    with file_lock:
                        print(text, end="", file=file_stream, flush=True)
                else:
                    print(text, end="", file=file_stream, flush=True)
            accumulator.append(text)

def extract_payload(output: str, max_input: int) -> str:
    """
    Intelligently extracts the head and tail of the unified output based on tokens.
    Uses an industry standard heuristic of 1 token ≈ 4 characters.
    Snaps cuts to newlines for readability.
    """
    if max_input <= 0:
        return ""

    text = output.strip()
    if not text:
        return "(no output captured)"

    max_chars = max_input * 4
    if len(text) <= max_chars:
        return text

    half = max_chars // 2

    # Grab head and tail
    head_raw = text[:half]
    tail_raw = text[-half:]

    # Snap to newlines if possible
    head = head_raw.rsplit('\n', 1)[0] if '\n' in head_raw else head_raw
    tail = tail_raw.split('\n', 1)[-1] if '\n' in tail_raw else tail_raw

    return f"{head}\n\n... [ TRUNCATED BY BRYTLOG: Exceeded token limit ] ...\n\n{tail}"
