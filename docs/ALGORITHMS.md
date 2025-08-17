# SagaTrans  Algorithmic Overview

This document explains the core algorithms and internal logic powering the SagaTrans application.

## 1. Translation Workflow Overview

1. **User loads or creates a project** with metadata (title description target language model context limit).
2. **User adds text items** to be translated.
3. **Token counts** are calculated for each item using `tiktoken`.
4. **User selects an item** and initiates translation.
5. **Context is dynamically constructed** from neighboring items respecting token limits.
6. **API request payload** is generated with the context and user message.
7. **Streaming translation** is received and displayed in real-time.
8. **Token counts update dynamically** during streaming.
9. **User saves the project** with updated translations.

---

## 2. Token Counting Logic

- Utilizes the `tiktoken` library to estimate the number of tokens in source and translated texts.
- If `tiktoken` fails to initialize falls back to a rough estimate: character count divided by 4.
- Token counts are stored per item and used to:
  - Display token info in the UI.
  - Calculate total project tokens.
  - Enforce context size limits during prompt construction.

---

## 3. Context Construction Algorithm

- **Goal:** Provide relevant context to improve translation quality without exceeding token limits.
- **Context Selection Modes:** The application supports different modes for selecting context items:
    - **Automatic (Fill Budget):** Includes nearby items until a target token budget (typically 80% of the project's context limit) is reached. It expands outward from the selected item adding items before and after as long as the budget allows.
    - **Automatic (Strict Nearby):** Includes a fixed number of items before and after the current item (currently 2 before and 2 after) regardless of the token budget.
    - **Manual (Checkboxes):** Allows users to manually select which items to include as context via checkboxes in the UI.
- **Process (Automatic Modes):**
  - Set a **target token budget** (for "Fill Budget" mode).
  - Start from the selected item.
  - Expand outward (for "Fill Budget") or select a fixed window (for "Strict Nearby").
  - For each candidate item:
    - Calculate its token count (source + translation).
    - **Skip** if adding it would exceed the budget (for "Fill Budget").
    - Otherwise include its source text and existing translation (if any) in the context.
  - Stop when the criteria for the selected mode are met.
- **Result:** A prompt containing the current item plus relevant context based on the selected mode.

---

## 4. API Request Generation

- Constructs a **system prompt** that:
  - Instructs the AI to translate the user message into the target language.
  - Includes the dynamically built context.
  - Emphasizes to **only return the translation** no explanations.
- **Prompt Templates:** The system prompt is constructed using templates that can be defined in `config.json` (for defaults) or overridden in the project settings. The system message is typically composed of a pre-context part the context items and a post-context part.
- The **user message** is the source text of the selected item formatted using a user prompt template.
- The payload is formatted as:
  ```json
  {
    "model": "model_name"
    "messages": [
      {"role": "system" "content": "constructed system prompt with context"}
      {"role": "user" "content": "source text"}
    ]
    "stream": true
  }
  ```
- Sent to the OpenRouter API with streaming enabled.

---

## 5. Streaming Translation Handling

- The API returns translation results **incrementally** (streaming).
- The app:
  - Receives chunks of translated text.
  - Appends them to the translation text area in real-time.
  - Updates token counts dynamically as new text arrives.
  - Enables a responsive UI experience.

---

## 6. Project and Item Management

- **Projects** are saved as JSON files containing:
  - Metadata (title description target language model context limit).
  - List of items with:
    - Name
    - Source text
    - Translated text
    - Approximate token count
- **Operations supported:**
  - Create load save delete projects.
  - Add rename reorder and remove items.
  - Edit project metadata.
- **Persistence:** Managed via `data_manager.py` which also handles loading configuration defaults.

---

## 7. Markdown Rendering

- Uses `markdown2` to convert source and translated text into HTML.
- Displayed in a dedicated **Markdown Preview** dialog.
- Helps visualize formatting headings lists etc. in translations.

---

## Summary

SagaTrans combines project management token-aware context building and real-time AI translation streaming to provide an efficient translation workflow. The algorithms prioritize relevant context within token limits to optimize translation quality.