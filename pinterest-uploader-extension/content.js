// content.js
//
// Pre-fills Pinterest pin creation form with data from the dashboard.
// Uses polling with MutationObserver fallback to wait for React SPA elements to mount.

function waitForElement(selector, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const element = document.querySelector(selector);
    if (element) return resolve(element);

    const observer = new MutationObserver(() => {
      const el = document.querySelector(selector);
      if (el) {
        observer.disconnect();
        resolve(el);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    setTimeout(() => {
      observer.disconnect();
      reject(new Error(`Element "${selector}" not found within ${timeout}ms`));
    }, timeout);
  });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Try to find Draft.js EditorState in the React fiber tree of the editor element.
 * This is a last-resort approach to directly update Draft.js state.
 */
function findDraftEditorState(contentEditable) {
  // Try to find the React fiber key on the element
  const reactKey = Object.keys(contentEditable).find(k => k.startsWith('__reactFiber$'));
  if (reactKey) {
    let fiber = contentEditable[reactKey];
    // Walk up the fiber tree looking for DraftEditor component
    let depth = 0;
    while (fiber && depth < 50) {
      const name = fiber.tag === 1 ? 'FunctionComponent' : 
                   fiber.tag === 0 ? 'Indeterminate' :
                   fiber.tag === 2 ? 'ClassComponent' :
                   fiber.tag === 3 ? 'HostRoot' :
                   fiber.tag === 5 ? 'HostComponent' :
                   fiber.tag === 6 ? 'HostText' :
                   fiber.tag === 10 ? 'ContextProvider' :
                   fiber.tag === 11 ? 'ContextConsumer' :
                   fiber.tag;
      const typeName = fiber.type?.name || fiber.type?.displayName || fiber.type?.toString().substring(0, 40) || 'N/A';
      
      if (fiber.memoizedState && fiber.memoizedState.queue) {
        console.log(`[DEBUG] fiber depth=${depth} tag=${name} type=${typeName} HAS memoizedState with queue`);
      } else if (fiber.memoizedState) {
        // Class component state - check for editorState
        let state = fiber.memoizedState;
        if (state && typeof state === 'object' && !Array.isArray(state)) {
          if (state.editorState || state._immutable) {
            console.log(`[DEBUG] fiber depth=${depth} tag=${name} type=${typeName} HAS editorState!`);
            return { fiber, state, editorState: state.editorState || state };
          }
          // Check linked list of hooks states
          let hook = fiber.memoizedState;
          while (hook) {
            if (hook.queue && hook.memoizedState) {
              const ms = hook.memoizedState;
              if (ms._immutable && typeof ms.getCurrentContent === 'function') {
                console.log(`[DEBUG] HOOK depth=${depth} type=${typeName} FOUND Draft.js EditorState via hook!`);
                return { fiber, state: ms, editorState: ms };
              }
              if (ms.constructor?.name === 'EditorState') {
                console.log(`[DEBUG] HOOK depth=${depth} type=${typeName} FOUND EditorState by constructor name`);
                return { fiber, state: ms, editorState: ms };
              }
            }
            hook = hook.next;
          }
        }
      }
      
      if (typeName && typeName.includes('Draft') || typeName.includes('Editor') && typeName.length < 30) {
        console.log(`[DEBUG] fiber depth=${depth} tag=${name} type=${typeName} — potential DraftEditor!`);
        // Check all state
        if (fiber.memoizedState) {
          let hook = fiber.memoizedState;
          let hookIdx = 0;
          while (hook) {
            console.log(`[DEBUG]   hook[${hookIdx}] memoizedState type:`, typeof hook.memoizedState, 
              hook.memoizedState?.constructor?.name,
              hook.memoizedState?._immutable !== undefined ? 'IMMUTABLE' : '');
            if (hook.memoizedState && hook.memoizedState._immutable !== undefined) {
              console.log(`[DEBUG]   hook[${hookIdx}] — FOUND Draft.js state!`);
              return { fiber, state: hook.memoizedState, editorState: hook.memoizedState };
            }
            hook = hook.next;
            hookIdx++;
          }
        }
      }
      fiber = fiber.return;
      depth++;
    }
  }
  
  // Also check for __reactInternalInstance$
  const reactInternalKey = Object.keys(contentEditable).find(k => k.startsWith('__reactInternalInstance$'));
  if (reactInternalKey) {
    let fiber = contentEditable[reactInternalKey];
    let depth = 0;
    while (fiber && depth < 50) {
      // Same check as above
      if (fiber.memoizedState) {
        let hook = fiber.memoizedState;
        let hookIdx = 0;
        while (hook) {
          if (hook.memoizedState && hook.memoizedState._immutable !== undefined) {
            console.log(`[DEBUG] internalInstance depth=${depth} hook[${hookIdx}] — FOUND Draft.js state!`);
            return { fiber, state: hook.memoizedState, editorState: hook.memoizedState };
          }
          hook = hook.next;
          hookIdx++;
        }
      }
      fiber = fiber.return;
      depth++;
    }
  }
  
  console.log("[DEBUG] No DraftEditor fiber found on contentEditable or its ancestors");
  return null;
}

function simulateInput(element, value) {
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value"
  )?.set;
  if (nativeInputValueSetter) {
    nativeInputValueSetter.call(element, value);
  } else {
    element.value = value;
  }
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

function uploadBase64Image(base64String) {
  const fileInput = document.querySelector('input[type="file"]');
  if (!fileInput) {
    console.error("Could not find Pinterest's image upload input.");
    return;
  }

  const parts = base64String.split(";base64,");
  const contentType = parts[0].split(":")[1];
  const rawBase64 = parts[1];

  const byteCharacters = atob(rawBase64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  const blob = new Blob([byteArray], { type: contentType });
  const file = new File([blob], "local_pin_image.jpg", { type: contentType });

  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  fileInput.files = dataTransfer.files;
  fileInput.dispatchEvent(new Event("change", { bubbles: true }));
}

/**
 * Watches for contenteditable attribute changes on Draft.js editor elements.
 * Helps identify what real user interaction activates the editor.
 */
function watchContentEditableChanges() {
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'attributes' && mutation.attributeName === 'contenteditable') {
        const el = mutation.target;
        const oldVal = mutation.oldValue;
        const newVal = el.getAttribute('contenteditable');
        const activeEl = document.activeElement;
        console.log("[ContentScript] [CE_WATCH] contenteditable changed on:", el.tagName,
          "class:", el.className?.substring(0, 40),
          "old:", oldVal, "-> new:", newVal,
          "activeElement:", activeEl?.tagName,
          "activeElement class:", activeEl?.className?.substring(0, 40));
        console.log("[ContentScript] [CE_WATCH] activeElement === changed element:", activeEl === el);
      }
    }
  });
  
  // Watch the entire body for contenteditable attribute changes
  observer.observe(document.body, {
    attributes: true,
    subtree: true,
    attributeFilter: ['contenteditable'],
    attributeOldValue: true,
  });
  
  console.log("[ContentScript] ContentEditable change watcher installed");
  return observer;
}

/**
 * Injects text into a Draft.js contenteditable editor using three strategies.
 *
 * BUG NOTES (do not reintroduce):
 *  - NEVER use document.execCommand('selectAll') — it selects the entire page when
 *    the contenteditable doesn't hold keyboard focus. Use window.getSelection()
 *    .selectAllChildren(element) instead; that is scoped to the element.
 *  - NEVER use new DataTransfer() for clipboardData on synthetic ClipboardEvents.
 *    In Chrome extension content scripts, DataTransfer.getData() returns "" when
 *    read back. Use Object.defineProperty to inject a plain-object mock instead.
 *  - Do NOT await between focus() and execCommand() — Pinterest can steal focus
 *    asynchronously before a setTimeout fires.
 */
async function setDraftJsText(element, text) {
  // ===== DEBUG: Log initial state =====
  console.log("[DEBUG] ===== setDraftJsText() invoked =====");
  console.log("[DEBUG] text.length:", text.length, "text:", text.substring(0, 100));
  console.log("[DEBUG] BEFORE — tagName:", element.tagName);
  console.log("[DEBUG] BEFORE — id:", element.id);
  console.log("[DEBUG] BEFORE — className:", element.className?.substring(0, 60));
  console.log("[DEBUG] BEFORE — isContentEditable:", element.isContentEditable);
  console.log("[DEBUG] BEFORE — contentEditable attr:", element.getAttribute('contenteditable'));
  console.log("[DEBUG] BEFORE — contentEditable attr value:", element.contentEditable);
  console.log("[DEBUG] BEFORE — offsetParent:", element.offsetParent?.tagName);
  const rect = element.getBoundingClientRect();
  console.log("[DEBUG] BEFORE — boundingClientRect:", JSON.stringify({x: rect.x, y: rect.y, w: rect.width, h: rect.height}));
  console.log("[DEBUG] BEFORE — document.activeElement:", (document.activeElement?.tagName || 'null') +
    (document.activeElement?.className ? '.' + document.activeElement.className?.substring(0, 40) : ''));
  console.log("[DEBUG] BEFORE — document.activeElement is contentEditable:", document.activeElement?.isContentEditable);
  console.log("[DEBUG] BEFORE — textContent:", element.textContent);
  console.log("[DEBUG] BEFORE — innerHTML (first 500):", element.innerHTML.substring(0, 500));
  console.log("[DEBUG] BEFORE — childNodes.length:", element.childNodes.length);
  for (let i = 0; i < element.childNodes.length && i < 5; i++) {
    const child = element.childNodes[i];
    console.log("[DEBUG] BEFORE — child[" + i + "]:", "nodeName=" + child.nodeName, "nodeType=" + child.nodeType,
      "textContent=" + (child.textContent?.substring(0, 40) || '""'));
  }

  // Check for React properties on the contentEditable element itself
  const ceOwnKeys = Object.getOwnPropertyNames(element);
  const ceReactFiber = ceOwnKeys.find(k => k.startsWith('__reactFiber$'));
  const ceReactProps = ceOwnKeys.find(k => k.startsWith('__reactProps$'));
  const ceReactInternal = ceOwnKeys.find(k => k.startsWith('__reactInternalInstance$'));
  if (ceReactFiber || ceReactProps || ceReactInternal) {
    console.log("[DEBUG] React props directly on contentEditable:",
      "fiber:", ceReactFiber ? "yes" : "no",
      "props:", ceReactProps ? Object.keys(element[ceReactProps]).filter(k => k.startsWith('on') || k === 'contentEditable').join(',') : "no",
      "internal:", ceReactInternal ? "yes" : "no");
  } else {
    console.log("[DEBUG] No React props directly on contentEditable");
  }

  console.log("[DEBUG] React keys on contentEditable:",
    element.hasAttribute('data-reactroot') ? "has data-reactroot" : "NONE");
  
  // Scan up to 10 ancestors for React fiber keys
  let ancestor = element.parentElement;
  let depth = 0;
  let foundReact = false;
  while (ancestor && depth < 10) {
    const fiberKey = ancestor.hasAttribute('data-reactroot') ? 'data-reactroot' :
      (ancestor.hasAttribute('data-reactid') ? 'data-reactid' : null);
    if (fiberKey) {
      console.log("[DEBUG] React key found at depth", depth, ":", fiberKey,
        "on tag:", ancestor.tagName, "class:", ancestor.className?.substring(0, 40));
      foundReact = true;
    }
    // Also check for __reactFiber$ properties (React 16+)
    const ownKeys = Object.getOwnPropertyNames(ancestor);
    const reactFiberKey = ownKeys.find(k => k.startsWith('__reactFiber$'));
    const reactPropsKey = ownKeys.find(k => k.startsWith('__reactProps$'));
    if (reactFiberKey) {
      const fiber = ancestor[reactFiberKey];
      if (fiber && fiber.memoizedState) {
        console.log("[DEBUG] React fiber found at depth", depth, ":",
          "tag:", ancestor.tagName, "class:", ancestor.className?.substring(0, 40));
        // Try to find EditorState in the fiber tree
        let stateNode = fiber;
        let searchDepth = 0;
        while (stateNode && searchDepth < 20) {
          if (stateNode.memoizedState) {
            const ms = stateNode.memoizedState;
            // Check if this looks like Draft.js EditorState (has _immutable or currentContent)
            const stateKeys = Object.keys(ms).filter(k => typeof k === 'string').join(',');
            if (stateKeys.includes('currentContent') || stateKeys.includes('_immutable')) {
              console.log("[DEBUG] Found Draft.js EditorState candidate at depth", depth,
                "fiber depth", searchDepth, "keys:", stateKeys.substring(0, 100));
            }
          }
          stateNode = stateNode.child;
          searchDepth++;
        }
        foundReact = true;
      }
    }
    if (reactPropsKey) {
      console.log("[DEBUG] React props found at depth", depth, ":",
        "tag:", ancestor.tagName, "class:", ancestor.className?.substring(0, 40),
        "props keys:", Object.keys(ancestor[reactPropsKey]).filter(k => k.startsWith('on') || k === 'contentEditable').join(','));
    }
    ancestor = ancestor.parentElement;
    depth++;
  }
  if (!foundReact) {
    console.log("[DEBUG] No React fiber keys found up to 10 ancestors");
  }

  // Try to find and log Draft.js EditorState
  const draftState = findDraftEditorState(element);
  if (draftState) {
    const es = draftState.editorState;
    console.log("[DEBUG] Draft.js EditorState found!");
    console.log("[DEBUG]   getCurrentContent:", es.getCurrentContent ? 'YES' : 'NO');
    try {
      const content = es.getCurrentContent();
      console.log("[DEBUG]   content blockMap:", content.getBlockMap ? 'YES' : 'NO');
      if (content.getBlockMap) {
        const blocks = content.getBlockMap();
        console.log("[DEBUG]   blockCount:", blocks.size || blocks.count ? blocks.size || blocks.count() : '?');
      }
    } catch(e) {
      console.log("[DEBUG]   Error accessing content:", e.message);
    }
  }

  // ===== FOCUS =====
  element.focus();
  await new Promise(r => setTimeout(r, 100));

  console.log("[DEBUG] AFTER FOCUS — document.activeElement:", (document.activeElement?.tagName || 'null') +
    (document.activeElement?.className ? '.' + document.activeElement.className?.substring(0, 40) : ''));
  console.log("[DEBUG] AFTER FOCUS — activeElement === contentEditable:", document.activeElement === element);
  console.log("[DEBUG] AFTER FOCUS — textContent:", element.textContent);

  // If focus didn't land on the contentEditable, try focusing again
  if (document.activeElement !== element) {
    console.log("[DEBUG] Focus didn't land on contentEditable, trying element.focus() again");
    element.focus();
    console.log("[DEBUG] AFTER RE-FOCUS — document.activeElement:", document.activeElement?.tagName,
      document.activeElement === element ? "(same)" : "DIFFERENT");
  }

  // ===== SELECT ALL CHILDREN (scoped to element) =====
  const range = document.createRange();
  range.selectNodeContents(element);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);

  console.log("[DEBUG] AFTER SELECTALL — selection.toString():", selection.toString().substring(0, 40));
  console.log("[DEBUG] AFTER SELECTALL — rangeCount:", selection.rangeCount);
  console.log("[DEBUG] AFTER SELECTALL — commonAncestor:", selection.getRangeAt(0)?.commonAncestorContainer?.nodeName);
  console.log("[DEBUG] AFTER SELECTALL — collapsed:", selection.getRangeAt(0)?.collapsed);
  console.log("[DEBUG] AFTER SELECTALL — startOffset:", selection.getRangeAt(0)?.startOffset, 
    "endOffset:", selection.getRangeAt(0)?.endOffset);
  console.log("[DEBUG] AFTER SELECTALL — startContainer:", selection.getRangeAt(0)?.startContainer?.nodeName);

  // ===== METHOD 1: Insert text via selection + execCommand =====
  // Clear existing content first
  document.execCommand('delete', false, null);
  
  // Insert text in chunks to match Draft.js expectations
  const result = document.execCommand('insertText', false, text);
  
  console.log("[DEBUG] METHOD 1 — execCommand('insertText') returned:", result);
  console.log("[DEBUG] METHOD 1 — textContent:", element.textContent.substring(0, 100));
  console.log("[DEBUG] METHOD 1 — document.activeElement:", (document.activeElement?.tagName || 'null') +
    (document.activeElement?.className ? '.' + document.activeElement.className?.substring(0, 40) : ''));
  
  const selAfter = window.getSelection();
  console.log("[DEBUG] METHOD 1 — selection toString:", selAfter.toString().substring(0, 40));
  console.log("[DEBUG] METHOD 1 — rangeCount:", selAfter.rangeCount);
  console.log("[DEBUG] METHOD 1 — selection collapsed:", selAfter.getRangeAt(0)?.collapsed);
  console.log("[DEBUG] METHOD 1 — innerHTML (first 500):", element.innerHTML.substring(0, 500));

  await new Promise(r => setTimeout(r, 100));
  console.log("[DEBUG] AFTER M1 WAIT — textContent:", element.textContent.substring(0, 100));
  console.log("[DEBUG] AFTER M1 WAIT — innerHTML (first 500):", element.innerHTML.substring(0, 500));
  console.log("[DEBUG] AFTER M1 WAIT — document.activeElement:", (document.activeElement?.tagName || 'null') +
    (document.activeElement?.className ? '.' + document.activeElement.className?.substring(0, 40) : ''));

  // Check if text was actually written
  if (element.textContent.trim().length > 0) {
    console.log("[ContentScript] Method 1 (execCommand) succeeded");
    return true;
  }

  // ===== METHOD 2: Direct DOM manipulation =====
  // If execCommand failed, try setting innerHTML directly
  console.log("[ContentScript] Method 1 failed. textContent:", element.textContent.substring(0, 100));
  
  try {
    // Escape HTML entities for safe insertion
    const escapedText = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
    
    // Build Draft.js-compatible innerHTML structure
    const editorId = element.getAttribute('data-editor') || 'editor';
    const blockKey = 'block-' + Math.random().toString(36).substring(2, 7);
    const offsetKey = blockKey + '-0-0';
    
    element.innerHTML = 
      '<div data-contents="true">' +
      '<div class="" data-block="true" data-editor="' + editorId + '" data-offset-key="' + offsetKey + '">' +
      '<div data-offset-key="' + offsetKey + '" class="public-DraftStyleDefault-block public-DraftStyleDefault-ltr">' +
      '<span data-offset-key="' + offsetKey + '">' + escapedText + '</span>' +
      '</div>' +
      '</div>' +
      '</div>';
    
    await new Promise(r => setTimeout(r, 100));
    console.log("[DEBUG] M2 innerHTML — textContent:", element.textContent.substring(0, 100));
    console.log("[DEBUG] M2 innerHTML — innerHTML (first 500):", element.innerHTML.substring(0, 500));
    
    if (element.textContent.trim().length > 0) {
      console.log("[ContentScript] Method 2 (innerHTML) succeeded");
      return true;
    }
  } catch (e) {
    console.log("[ContentScript] Method 2 failed:", e.message);
  }

  // ===== METHOD 3: textContent =====
  console.log("[ContentScript] Method 2 failed. textContent:", element.textContent.substring(0, 100));
  try {
    element.textContent = text;
    await new Promise(r => setTimeout(r, 100));
    console.log("[DEBUG] M3 textContent — textContent:", element.textContent.substring(0, 100));
    
    if (element.textContent.trim().length > 0) {
      console.log("[ContentScript] Method 3 (textContent) succeeded");
      return true;
    }
  } catch (e) {
    console.log("[ContentScript] Method 3 failed:", e.message);
  }

  // ===== FINAL STATE DUMP =====
  console.log("[DEBUG] ===== FINAL STATE DUMP =====");
  console.log("[DEBUG] FINAL — tagName:", element.tagName);
  console.log("[DEBUG] FINAL — id:", element.id);
  console.log("[DEBUG] FINAL — className:", element.className?.substring(0, 60));
  console.log("[DEBUG] FINAL — isContentEditable:", element.isContentEditable);
  console.log("[DEBUG] FINAL — contentEditable attr:", element.getAttribute('contenteditable'));
  console.log("[DEBUG] FINAL — innerHTML (first 500):", element.innerHTML.substring(0, 500));
  console.log("[DEBUG] FINAL — textContent:", element.textContent.substring(0,100));
  console.log("[DEBUG] FINAL — childNodes.length:", element.childNodes.length);
  for (let i = 0; 
  i < element.childNodes.length && i < 5; i++) { const child = 
    element.childNodes[i]; console.log("[DEBUG] FINAL - child[" + i + "]:", "nodeName=" + child.nodeName, "nodeType=" + child.nodeType, "textContent=" + (child.textContent?.substring(0, 40) || '""')); } console.log("[DEBUG] FINAL — document.activeElement:", (document.activeElement?.tagName || 'null') + (document.activeElement?.className ? '.' + document.activeElement.className?.substring(0, 40) : '')); console.log("[DEBUG] FINAL — activeElement === contentEditable:", document.activeElement === element); console.log("[DEBUG] FINAL — React keys on contentEditable:", element.hasAttribute('data-reactroot') ? "has data-reactroot" : "NONE"); const finalOwnKeys = Object.getOwnPropertyNames(element); const finalCeReactFiber = finalOwnKeys.find(k => k.startsWith('__reactFiber$')); const finalCeReactProps = finalOwnKeys.find(k => k.startsWith('__reactProps$')); if (finalCeReactFiber || finalCeReactProps) { console.log("[DEBUG] FINAL — React fiber:", finalCeReactFiber ? "yes" : "no", "React props:", finalCeReactProps ? "yes" : "no"); } const finalAttrs = []; for (const attr of element.attributes) { finalAttrs.push(attr.name + "=\"" + attr.value + "\""); } console.log("[DEBUG] FINAL — all attributes:", finalAttrs.join(", "));

  return false;
}

async function prefillPinData(data) {
  console.log("[ContentScript] Starting prefill with data:", {
    title: data.title?.substring(0, 50),
    description: data.description?.substring(0, 50),
    url: data.url,
    hasImage: !!data.imageBase64,
  });

  const results = {};

  // 1. Set Title
  try {
    const titleInput = await waitForElement('#storyboard-selector-title');
    simulateInput(titleInput, data.title);
    results.title = "ok";
    console.log("[ContentScript] Title set successfully");
  } catch (err) {
    results.title = "error: " + err.message;
    console.warn("[ContentScript] Failed to set title:", err.message);
  }

  // 2. Set Description (Draft.js editor)
  try {
    const descContainer = await waitForElement('#dweb-comment-editor-container');
    console.log("[ContentScript] Found description container");

    // The Draft.js editor has a two-layer structure:
    // 1. An overlay div[role="button"] that captures clicks before activation
    // 2. The actual .public-DraftEditor-content which gets contenteditable="true" after activation
    // We need to click the overlay button to activate the editor.
    
    // Find the overlay button — it's a div[role="button"] in the PARENT container
    // (div[data-test-id="storyboard-description-field-container"]), NOT inside
    // #dweb-comment-editor-container. We search the whole page for the right one.
    const storyboardContainer = document.querySelector(
      'div[data-test-id="storyboard-description-field-container"]'
    );
    const overlayButton = storyboardContainer 
      ? storyboardContainer.querySelector('div[aria-disabled="false"][role="button"]')
      : null;
    
    if (overlayButton) {
      console.log("[ContentScript] Found overlay button, clicking to activate editor");
      // Use real browser click with all proper event properties
      overlayButton.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window, clientX: 0, clientY: 0 }));
      overlayButton.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window, clientX: 0, clientY: 0 }));
      overlayButton.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window, clientX: 0, clientY: 0 }));
    } else {
      console.log("[ContentScript] No overlay button found, trying direct click on container");
      descContainer.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
      descContainer.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
      descContainer.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    }
    
    // After clicking the overlay, React needs time to re-render the editor.
    // Wait for the render to complete, then find the NEW editor element.
    await new Promise(r => setTimeout(r, 2000));
    
    // Now find the contentEditable element in the NEW render tree
    let contentEditable = descContainer.querySelector(
      '[contenteditable="true"], ' +
      '.public-DraftEditor-content, ' +
      '[aria-label*="опис" i], ' +
      '[aria-label*="description" i]'
    );

    if (!contentEditable) {
      console.log("[ContentScript] contentEditable not immediately available, waiting…");
      contentEditable = await waitForElement(
        '#dweb-comment-editor-container [contenteditable="true"], ' +
        '#dweb-comment-editor-container .public-DraftEditor-content',
        10000
      );
    }

    if (!contentEditable) throw new Error("Could not find contentEditable element");

    console.log("[ContentScript] contentEditable found — tag:", contentEditable.tagName,
      "class:", contentEditable.className?.substring(0, 60),
      "contentEditable attr:", contentEditable.getAttribute('contenteditable'),
      "data-editor:", contentEditable.querySelector('[data-editor]')?.getAttribute('data-editor') || 'N/A');

    // If still contenteditable="false", try focusing directly
    if (contentEditable.getAttribute('contenteditable') !== 'true') {
      console.log("[ContentScript] contentEditable is not 'true', trying direct focus");
      contentEditable.focus();
      await new Promise(r => setTimeout(r, 300));
      // If still not true, force it
      if (contentEditable.getAttribute('contenteditable') !== 'true') {
        console.log("[ContentScript] Still not 'true', forcing via setAttribute");
        contentEditable.setAttribute('contenteditable', 'true');
      }
    }

    const ok = await setDraftJsText(contentEditable, data.description);

    if (!ok) {
      throw new Error("All three injection methods failed to produce text in the editor");
    }

    results.description = "ok";
    console.log("[ContentScript] Description set. Preview:", contentEditable.textContent.substring(0, 60));
  } catch (err) {
    results.description = "error: " + err.message;
    console.warn("[ContentScript] Failed to set description:", err.message);
  }

  // 3. Set Destination URL
  try {
    let urlInput = null;

    const urlSelector = (
      'input[placeholder*="link" i], ' +
      'input[placeholder*="url" i], ' +
      'input[placeholder*="website" i], ' +
      'input[aria-label*="link" i], ' +
      'input[aria-label*="url" i], ' +
      'input[name*="link" i], ' +
      'input[name*="url" i], ' +
      'textarea[placeholder*="link" i], ' +
      'textarea[placeholder*="url" i], ' +
      'textarea[aria-label*="link" i], ' +
      'textarea[aria-label*="url" i], ' +
      '[data-testid*="link" i] input, ' +
      '[data-testid*="url" i] input, ' +
      '[data-testid*="link" i] textarea, ' +
      '[data-testid*="url" i] textarea'
    );

    try {
      urlInput = await waitForElement(urlSelector, 10000);
    } catch (e) {
      console.log("[ContentScript] URL not found via specific selectors, trying broader search");
    }

    if (!urlInput) {
      const allInputs = document.querySelectorAll('input, textarea');
      for (const el of allInputs) {
        if (el.id === 'storyboard-selector-title') continue;
        if (el.type === 'hidden') continue;
        if (el.type === 'file') continue;
        if (el.type === 'checkbox') continue;
        if (el.type === 'radio') continue;
        if (el.id.toLowerCase().includes('search')) continue;
        if ((el.placeholder || '').toLowerCase().includes('search')) continue;
        if ((el.name || '').toLowerCase().includes('search')) continue;
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          urlInput = el;
          console.log("[ContentScript] Found URL input via broad search:", el.id, el.placeholder, el.name, el.type);
          break;
        }
      }
    }

    if (urlInput) {
      simulateInput(urlInput, data.url);
      results.url = "ok";
      console.log("[ContentScript] URL set successfully");
    } else {
      throw new Error("Could not find any URL/link input field on the page");
    }
  } catch (err) {
    results.url = "error: " + err.message;
    console.warn("[ContentScript] Failed to set URL:", err.message);
  }

  // 4. Upload Image
  if (data.imageBase64) {
    try {
      await new Promise((r) => setTimeout(r, 2000));
      uploadBase64Image(data.imageBase64);
      results.image = "ok";
      console.log("[ContentScript] Image uploaded successfully");
    } catch (err) {
      results.image = "error: " + err.message;
      console.warn("[ContentScript] Failed to upload image:", err.message);
    }
  }

  console.log("[ContentScript] Prefill results:", results);
  return results;
}

// --- Message Listener ---
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "prefill") {
    prefillPinData(request.data).then((results) => {
      console.log("[ContentScript] Prefill completed:", results);

      // ===== DELAYED STATE CHECK (watch for React re-render clearing the field) =====
      setTimeout(() => {
        const descContainer = document.querySelector('#dweb-comment-editor-container');
        if (descContainer) {
          const ce = descContainer.querySelector('.public-DraftEditor-content') || 
                     descContainer.querySelector('[contenteditable="true"]');
          if (ce) {
            console.log("[ContentScript] [DELAYED] 0s — contentEditable:", ce.getAttribute('contenteditable'),
              "textContent:", (ce.textContent || '').substring(0, 60),
              "innerHTML:", ce.innerHTML.substring(0, 100));
          }
        }
      }, 100);

      setTimeout(() => {
        const descContainer = document.querySelector('#dweb-comment-editor-container');
        if (descContainer) {
          const ce = descContainer.querySelector('.public-DraftEditor-content') || 
                     descContainer.querySelector('[contenteditable="true"]');
          if (ce) {
            console.log("[ContentScript] [DELAYED] 1s — contentEditable:", ce.getAttribute('contenteditable'),
              "textContent:", (ce.textContent || '').substring(0, 60));
          }
        }
      }, 1000);

      setTimeout(() => {
        const descContainer = document.querySelector('#dweb-comment-editor-container');
        if (descContainer) {
          const ce = descContainer.querySelector('.public-DraftEditor-content') || 
                     descContainer.querySelector('[contenteditable="true"]');
          if (ce) {
            console.log("[ContentScript] [DELAYED] 2s — contentEditable:", ce.getAttribute('contenteditable'),
              "textContent:", (ce.textContent || '').substring(0, 60));
          }
        }
      }, 2000);

      setTimeout(() => {
        const descContainer = document.querySelector('#dweb-comment-editor-container');
        if (descContainer) {
          const ce = descContainer.querySelector('.public-DraftEditor-content') || 
                     descContainer.querySelector('[contenteditable="true"]');
          if (ce) {
            console.log("[ContentScript] [DELAYED] 5s — contentEditable:", ce.getAttribute('contenteditable'),
              "textContent:", (ce.textContent || '').substring(0, 60));
          }
        }
        console.log("[ContentScript] [DELAYED] Done watching");
      }, 5000);
    });
    sendResponse({ status: "success" });
  }
});

// Start watching for contenteditable changes to diagnose activation
watchContentEditableChanges();

// Log what element was clicked
document.addEventListener('click', (e) => {
  const target = e.target;
  console.log("[ContentScript] [CLICK] clicked on:", target.tagName,
    "id:", target.id,
    "class:", target.className?.substring(0, 40));
}, true); // useCapture = true to catch all clicks

console.log("[ContentScript] Pinterest Pre-filler content script loaded.");