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
  
  // Also watch all DOM changes on the editor container
  watchAllDOMChanges();
  
  return observer;
}

/**
 * Watches ALL DOM changes on the editor container to understand Pinterest's
 * activation mechanism. This is a diagnostic tool.
 */
function watchAllDOMChanges() {
  const container = document.querySelector('#dweb-comment-editor-container');
  if (!container) {
    // Retry after a delay
    setTimeout(watchAllDOMChanges, 2000);
    return;
  }
  
  console.log("[ContentScript] [DOM_WATCH] Starting comprehensive DOM watch on editor container");
  
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'attributes') {
        const el = mutation.target;
        console.log("[DOM_WATCH] ATTR:", mutation.attributeName,
          "on:", el.tagName,
          "class:", el.className?.substring(0, 30),
          "old:", mutation.oldValue?.substring(0, 50),
          "new:", el.getAttribute(mutation.attributeName)?.substring(0, 50));
      } else if (mutation.type === 'childList') {
        const added = mutation.addedNodes.length;
        const removed = mutation.removedNodes.length;
        if (added > 0 || removed > 0) {
          console.log("[DOM_WATCH] CHILD:", 
            "added:", added, 
            "removed:", removed,
            "on:", mutation.target.tagName,
            "class:", mutation.target.className?.substring(0, 30));
          for (const node of mutation.addedNodes) {
            if (node.nodeType === 1) { // Element
              console.log("[DOM_WATCH]   + added:", node.tagName,
                "class:", node.className?.substring(0, 40),
                "id:", node.id || 'none');
            }
          }
        }
      } else if (mutation.type === 'characterData') {
        console.log("[DOM_WATCH] TEXT:", 
          "data:", mutation.target.textContent?.substring(0, 40),
          "parent:", mutation.target.parentElement?.tagName,
          "parent class:", mutation.target.parentElement?.className?.substring(0, 30));
      }
    }
  });
  
  observer.observe(container, {
    attributes: true,
    childList: true,
    subtree: true,
    characterData: true,
    attributeOldValue: true,
  });
  
  return observer;
}

/**
 * Injects text into a Draft.js contenteditable editor.
 *
 * Uses clipboard API + paste event as the primary strategy, because Draft.js
 * handles paste events natively (extracts text from clipboardData and inserts
 * it into EditorState, updating React state directly).
 *
 * BUG NOTES (do not reintroduce):
 *  - NEVER use document.execCommand('selectAll') — it selects the entire page when
 *    the contenteditable doesn't hold keyboard focus. Use window.getSelection()
 *    .selectAllChildren(element) instead; that is scoped to the element.
 *  - NEVER use new DataTransfer() for clipboardData on synthetic ClipboardEvents.
 *    In Chrome extension content scripts, DataTransfer.getData() returns "" when
 *    read back. Use Object.defineProperty to inject a mock instead.
 *  - Do NOT use setAttribute('contenteditable', 'true') as the primary approach —
 *    it triggers React to remount the DraftEditor component, wiping any text.
 *    The paste method works even when contenteditable is "false".
 */
async function setDraftJsText(element, text) {
  // ===== DEBUG: Log initial state =====
  console.log("[DEBUG] ===== setDraftJsText() invoked =====");
  console.log("[DEBUG] text.length:", text.length, "text:", text.substring(0, 100));
  console.log("[DEBUG] BEFORE — tagName:", element.tagName);
  console.log("[DEBUG] BEFORE — className:", element.className?.substring(0, 60));
  console.log("[DEBUG] BEFORE — isContentEditable:", element.isContentEditable);
  console.log("[DEBUG] BEFORE — contentEditable attr:", element.getAttribute('contenteditable'));
  console.log("[DEBUG] BEFORE — textContent:", element.textContent);
  
  // ===== Try paste-based approach first (bypasses contenteditable check) =====
  try {
    // Step 1: Focus the element
    element.focus();
    await new Promise(r => setTimeout(r, 50));
    
    // Step 2: Write to clipboard
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      console.log("[DEBUG] PASTE — wrote text to clipboard");
    } else {
      console.log("[DEBUG] PASTE — clipboard API not available");
      return await fallbackSetDraftJsText(element, text);
    }
    
    // Step 3: Create clipboardData mock for the paste event
    // Chrome extensions can't read DataTransfer.getData() from synthetic events,
    // so we use Object.defineProperty to inject a mock.
    const clipboardData = new DataTransfer();
    clipboardData.setData('text/plain', text);
    
    // Override getData to return our text
    const originalGetData = clipboardData.getData.bind(clipboardData);
    Object.defineProperty(clipboardData, 'getData', {
      value: function(type) {
        console.log("[DEBUG] PASTE — getData called with type:", type);
        if (type === 'text/plain' || type === 'text') {
          return text;
        }
        return originalGetData(type);
      },
      writable: false,
      configurable: true,
    });
    
    // Step 4: Select all existing content (to be replaced by paste)
    const range = document.createRange();
    range.selectNodeContents(element);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    
    // Step 5: Dispatch paste event
    const pasteEvent = new ClipboardEvent('paste', {
      clipboardData: clipboardData,
      bubbles: true,
      cancelable: true,
      composed: true,
    });
    
    element.dispatchEvent(pasteEvent);
    console.log("[DEBUG] PASTE — dispatched paste event");
    
    // Step 6: Wait for Draft.js to process
    await new Promise(r => setTimeout(r, 200));
    
    console.log("[DEBUG] PASTE — textContent after paste:", element.textContent.substring(0, 100));
    console.log("[DEBUG] PASTE — innerHTML (first 500):", element.innerHTML.substring(0, 500));
    
    if (element.textContent.trim().length > 0) {
      console.log("[ContentScript] Paste method succeeded");
      return true;
    }
    
    console.log("[ContentScript] Paste method produced no text, trying execCommand fallback");
  } catch (e) {
    console.log("[DEBUG] PASTE — Error:", e.message);
  }
  
  // ===== Fallback: Use the existing execCommand approach =====
  return await fallbackSetDraftJsText(element, text);
}

/**
 * Fallback method: use execCommand('insertText') after ensuring
 * contentEditable is 'true'. Note: this may trigger React remount.
 */
async function fallbackSetDraftJsText(element, text) {
  // Ensure contentEditable is true (may trigger React remount)
  if (element.getAttribute('contenteditable') !== 'true') {
    element.setAttribute('contenteditable', 'true');
    await new Promise(r => setTimeout(r, 50));
  }
  
  console.log("[DEBUG] FALLBACK — contentEditable attr:", element.getAttribute('contenteditable'));
  console.log("[DEBUG] FALLBACK — textContent:", element.textContent);
  console.log("[DEBUG] FALLBACK — innerHTML (first 500):", element.innerHTML.substring(0, 500));
  
  // Focus the element
  element.focus();
  console.log("[DEBUG] FALLBACK AFTER FOCUS — document.activeElement:", 
    (document.activeElement?.tagName || 'null') +
    (document.activeElement?.className ? '.' + document.activeElement.className?.substring(0, 40) : ''));
  console.log("[DEBUG] FALLBACK AFTER FOCUS — activeElement === contentEditable:", document.activeElement === element);
  
  // Select all children
  const range = document.createRange();
  range.selectNodeContents(element);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  
  console.log("[DEBUG] FALLBACK AFTER SELECTALL — selection.toString():", selection.toString().substring(0, 40));
  
  // Clear and insert text
  document.execCommand('delete', false, null);
  const result = document.execCommand('insertText', false, text);
  
  console.log("[DEBUG] FALLBACK — execCommand('insertText') returned:", result);
  console.log("[DEBUG] FALLBACK — textContent:", element.textContent.substring(0, 100));
  console.log("[DEBUG] FALLBACK — innerHTML (first 500):", element.innerHTML.substring(0, 500));
  
  // Dispatch InputEvent for Draft.js
  try {
    const inputEvent = new InputEvent('input', {
      inputType: 'insertText',
      data: text,
      bubbles: true,
      cancelable: true,
      composed: true,
    });
    element.dispatchEvent(inputEvent);
    console.log("[DEBUG] FALLBACK — dispatched InputEvent");
  } catch(e) {
    console.log("[DEBUG] FALLBACK — Error dispatching InputEvent:", e.message);
  }
  
  await new Promise(r => setTimeout(r, 100));
  
  if (element.textContent.trim().length > 0) {
    console.log("[ContentScript] Fallback method succeeded");
    return true;
  }
  
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
      // Use native .click() which is trusted (isTrusted=true) and triggers
      // proper browser focus behavior. dispatchEvent with synthetic MouseEvent
      // has isTrusted=false which breaks React's focus handling.
      overlayButton.click();
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

    // Note: The editor's contenteditable attribute naturally stays "false" on Pinterest.
    // Our setDraftJsText function will try paste-based injection first (no contenteditable
    // needed), then fall back to execCommand with setAttribute if paste fails.
    console.log("[ContentScript] Editor found, contentEditable attr:", 
      contentEditable.getAttribute('contenteditable'), "- proceeding with setDraftJsText");

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
  console.log("[ContentScript] [CLICK] clicked on:", e.target.tagName,
    "id:", e.target.id || '',
    "class:", e.target.className?.substring(0, 60) || '',
    "isTrusted:", e.isTrusted);
}, true); // useCapture = true to catch all clicks

console.log("[ContentScript] Pinterest Pre-filler content script loaded.");