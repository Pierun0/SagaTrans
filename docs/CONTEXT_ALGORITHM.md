# SagaTrans — Context Construction Algorithm

This document provides an in-depth explanation of how SagaTrans builds the context for translation prompts including ASCII illustrations.

---

## 1. Introduction

To improve translation quality SagaTrans includes **relevant context** from neighboring text items when translating a selected item. This helps the AI model understand the surrounding content maintain consistency and produce more accurate translations.

---

## 2. Token Budgeting

- Each AI model has a **context token limit**.
- SagaTrans uses **approximately 80%** of this limit for context to leave room for the actual translation.
- The **target token budget** is calculated as:

```
target_budget = context_token_limit * 0.8
```

- The algorithm adds context items **until** this budget is reached or exceeded.

---

## 3. Step-by-Step Process

### Initial State

```
[Item 1] [Item 2] [Selected Item] [Item 4] [Item 5]
```

### Step 1: Start with the Selected Item

```
                [Selected Item]
```

### Step 2: Expand Outward

- Add immediate neighbors **before and after** the selected item **if** their combined tokens **do not exceed** the budget.

```
          [Item 2] [Selected Item] [Item 4]
```

### Step 3: Continue Expanding

- Add the next neighbors outward checking the budget **each time**.

```
[Item 1] [Item 2] [Selected Item] [Item 4] [Item 5]
```

### Step 4: Budget Check

- **If** adding an item **exceeds** the budget **skip** it.
- The process **stops** when no more items can be added without exceeding the budget.

### Final Context Example

```
[Included Item(s)] ... [Selected Item] ... [Included Item(s)]
```

---

## 4. Context Selection Modes

### Automatic (Fill Budget) - Default Mode
```python
context_items = [selected_item]
budget_used = token_count(selected_item)

offset = 1
while True:
    added = False
    # Check item before
    before_index = selected_index - offset
    if before_index >= 0:
        tokens = token_count(items[before_index])
        if budget_used + tokens <= target_budget:
            context_items.insert(0 items[before_index])
            budget_used += tokens
            added = True
    # Check item after
    after_index = selected_index + offset
    if after_index < len(items):
        tokens = token_count(items[after_index])
        if budget_used + tokens <= target_budget:
            context_items.append(items[after_index])
            budget_used += tokens
            added = True
    if not added:
        break
    offset += 1
```

### Automatic (Strict Nearby) Mode
Includes nearby items (aiming for a window around the current item) while still respecting the overall context token budget. It expands outward from the selected item adding items before and after as long as the budget allows.

```python
# Simplified representation of the logic
context_items = {selected_index} # Start with the current item index
current_token_count = 0 # Tracks tokens of *context* items only
target_token_budget = context_limit # Use the full limit for context items

left right = selected_index - 1 selected_index + 1

while (left >= 0 or right < len(items)):
    added_in_iteration = False

    # Try to add the item to the right (next)
    if right < len(items):
        item = items[right]
        item_tokens = count_tokens(item.get('source_text' '')) + \
                     count_tokens(item.get('translated_text' ''))

        if current_token_count + item_tokens <= target_token_budget:
            context_items.add(right)
            current_token_count += item_tokens
            added_in_iteration = True
        right += 1 # Always move to the next item on the right

    # Try to add the item to the left (previous)
    if left >= 0:
        item = items[left]
        item_tokens = count_tokens(item.get('source_text' '')) + \
                     count_tokens(item.get('translated_text' ''))

        if current_token_count + item_tokens <= target_token_budget:
            context_items.add(left)
            current_token_count += item_tokens
            added_in_iteration = True
        left -= 1 # Always move to the next item on the left

    if not added_in_iteration and (left < 0 and right >= len(items)):
        break # No more items to check
    elif not added_in_iteration:
        break # Couldn't add any items due to budget stop expanding

# The final context items are those with indices in the context_items set.
```

### Manual (Checkboxes) Mode
Users manually select which items to include as context via checkboxes in the UI.

---

## 5. Mode Selection

Users can choose between three context selection modes:

1. **Automatic (Fill Budget)** - Default mode that includes nearby items until token budget is nearly full
2. **Automatic (Strict Nearby)** - Includes exactly 2 items before and 2 items after current item
3. **Manual (Checkboxes)** - Users manually select which items to include

## 6. Resulting Prompt Structure

- The included context is formatted with clear separators for example:

```
==================== CONTEXT ITEM START: Chapter 2 ====================
Source Text:
Once upon a time there was a brave knight...

Existing Translation:
Il était une fois un chevalier courageux...

==================== CONTEXT ITEM END: Chapter 2 ======================

==================== CONTEXT ITEM START: Chapter 3 ====================
Source Text:
The knight ventured into the dark forest...

Existing Translation:
Le chevalier s'aventura dans la forêt sombre...

==================== CONTEXT ITEM END: Chapter 3 ======================

==================== CONTEXT ITEM START: Chapter 4 (Selected) ====================
Source Text:
Suddenly a dragon appeared before him...

Existing Translation:
(Empty to be generated)

==================== CONTEXT ITEM END: Chapter 4 (Selected) ======================

==================== CONTEXT ITEM START: Chapter 5 ====================
Source Text:
The knight raised his sword ready to fight...

Existing Translation:
Le chevalier leva son épée prêt à se battre...

==================== CONTEXT ITEM END: Chapter 5 ======================
```

- The **system prompt** contains all included context plus instructions to translate the selected item.

- This structure helps the AI understand the flow of the story or document improving translation coherence.

---

## 7. Related Files

- [Main Project Overview (README.md)](README.md)
- [Algorithmic Overview (ALGORITHMS.md)](ALGORITHMS.md)
- [This Context Algorithm Explanation (CONTEXT_ALGORITHM.md)](CONTEXT_ALGORITHM.md)

---

## 8. Test Cases

### Automatic (Fill Budget) Mode
1. **Normal Case**: Middle item with sufficient context
   - Includes items until token budget is nearly full
   - Balances items before/after current item
2. **Edge Case**: First item in list
   - Only includes items after current item
3. **Edge Case**: Last item in list
   - Only includes items before current item
4. **Token Limit**: When context would exceed limit
   - Stops including items before hitting limit

### Automatic (Strict Nearby) Mode
1. **Normal Case**: Middle item
   - Includes exactly 2 items before and 2 items after
2. **Edge Case**: First item
   - Includes up to 2 items after
3. **Edge Case**: Last item
   - Includes up to 2 items before
4. **Short List**: Fewer than 5 items total
   - Includes all available items

### Manual (Checkboxes) Mode
1. **Selection**: Any combination of items can be included
   - Completely user-controlled
   - No automatic token counting

## 9. Summary

- The algorithm **prioritizes nearby items** to provide the most relevant context.
- It **respects token limits** to avoid exceeding model constraints.
- This approach **improves translation quality** by leveraging surrounding content without overwhelming the model.