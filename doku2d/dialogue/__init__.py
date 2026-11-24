"""Dialogue trees and a ready-to-use in-game dialogue control."""
from .tree import DialogueCall, DialogueChoice, DialogueFormatError, DialogueInput, DialogueLine, DialogueSection, DialogueTree
from .box import DialogueBox, DialogueHistoryEntry
from .widgets import DialogueHistory, SpeechBubble
from .analysis import DialogueWarning, analyze_dialogue
from .graph import DialogueGraph

__all__ = ["DialogueBox", "DialogueChoice", "DialogueFormatError", "DialogueLine",
           "DialogueSection", "DialogueTree", "DialogueCall", "DialogueInput", "DialogueHistory", "DialogueHistoryEntry",
           "SpeechBubble", "DialogueGraph", "DialogueWarning", "analyze_dialogue"]
