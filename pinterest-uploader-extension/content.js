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
async function setDraftJsText(contentEditable, text) {
  // ── [DEBUG] Step 0: Full element dump BEFORE any manipulation ────────────────
  console.log("[DEBUG] ===== setDraftJsText() invoked =====");
  console.log("[DEBUG] text.length:", text.length, "text:", JSON.stringify(text.substring(0, 120)));
  console.log("[DEBUG] BEFORE — tagName:", contentEditable.tagName);
  console.log("[DEBUG] BEFORE — id:", contentEditable.id);
  console.log("[DEBUG] BEFORE — className:", contentEditable.className);
  console.log("[DEBUG] BEFORE — isContentEditable:", contentEditable.isContentEditable);
  console.log("[DEBUG] BEFORE — contentEditable attr:", contentEditable.getAttribute('contenteditable'));
  console.log("[DEBUG] BEFORE — offsetParent:", contentEditable.offsetParent ? contentEditable.offsetParent.tagName : null);
  const bcr = contentEditable.getBoundingClientRect();
  console.log("[DEBUG] BEFORE — boundingClientRect:", JSON.stringify({ x: bcr.x, y: bcr.y, w: bcr.width, h: bcr.height }));
  console.log("[DEBUG] BEFORE — document.activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : null);
  console.log("[DEBUG] BEFORE — document.activeElement is contentEditable:", document.activeElement === contentEditable);
  console.log("[DEBUG] BEFORE — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));
  console.log("[DEBUG] BEFORE — innerHTML (first 500):", JSON.stringify(contentEditable.innerHTML.substring(0, 500)));
  console.log("[DEBUG] BEFORE — childNodes.length:", contentEditable.childNodes.length);
  for (let i = 0; i < contentEditable.childNodes.length; i++) {
    const cn = contentEditable.childNodes[i];
    console.log("[DEBUG] BEFORE — child[" + i + "]: nodeName=" + cn.nodeName + " nodeType=" + cn.nodeType + " textContent=" + JSON.stringify((cn.textContent || '').substring(0, 60)));
  }

  contentEditable.scrollIntoView({ behavior: 'instant', block: 'nearest' });
  await new Promise(r => setTimeout(r, 100));

  // ── [DEBUG] Check for React fiber keys on the element and ancestors ──────────
  const allKeys = Object.keys(contentEditable).filter(k => k.startsWith('__react'));
  console.log("[DEBUG] React keys on contentEditable:", allKeys.length > 0 ? allKeys : 'NONE');
  let parent = contentEditable.parentElement;
  let depth = 0;
  while (parent && depth < 5) {
    const parentKeys = Object.keys(parent).filter(k => k.startsWith('__react'));
    if (parentKeys.length > 0) {
      console.log("[DEBUG] React keys on ancestor depth=" + depth + " tag=" + parent.tagName + ":", parentKeys);
    }
    parent = parent.parentElement;
    depth++;
  }
  if (depth === 5) console.log("[DEBUG] No React fiber keys found up to 5 ancestors");

  // ── Method 1: selectAllChildren (scoped) + execCommand('insertText') ──────────
  // focus() and selection must be set synchronously — no await in between —
  // so Pinterest's React code cannot steal focus before execCommand fires.
  contentEditable.focus();

  // [DEBUG] After focus()
  await new Promise(r => setTimeout(r, 0)); // yield once to let React process focus
  console.log("[DEBUG] AFTER FOCUS — document.activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') + (document.activeElement.className ? '.' + document.activeElement.className.substring(0, 40) : '') : null);
  console.log("[DEBUG] AFTER FOCUS — activeElement === contentEditable:", document.activeElement === contentEditable);
  console.log("[DEBUG] AFTER FOCUS — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));

  window.getSelection().selectAllChildren(contentEditable);

  // [DEBUG] After selectAllChildren()
  const sel = window.getSelection();
  console.log("[DEBUG] AFTER SELECTALL — selection.toString():", JSON.stringify(sel.toString().substring(0, 80)));
  console.log("[DEBUG] AFTER SELECTALL — rangeCount:", sel.rangeCount);
  if (sel.rangeCount > 0) {
    const range = sel.getRangeAt(0);
    console.log("[DEBUG] AFTER SELECTALL — commonAncestor:", range.commonAncestorContainer ? range.commonAncestorContainer.nodeName : null);
    console.log("[DEBUG] AFTER SELECTALL — collapsed:", range.collapsed);
    console.log("[DEBUG] AFTER SELECTALL — startOffset:", range.startOffset, "endOffset:", range.endOffset);
    console.log("[DEBUG] AFTER SELECTALL — startContainer:", range.startContainer ? range.startContainer.nodeName + (range.startContainer.textContent ? ' "' + range.startContainer.textContent.substring(0, 40) + '"' : '') : null);
  }

  const m1Result = document.execCommand('insertText', false, text);

  // [DEBUG] After execCommand
  console.log("[DEBUG] METHOD 1 — execCommand('insertText') returned:", m1Result);
  console.log("[DEBUG] METHOD 1 — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));
  console.log("[DEBUG] METHOD 1 — document.activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : null);
  const selAfter = window.getSelection();
  console.log("[DEBUG] METHOD 1 — selection toString:", JSON.stringify(selAfter.toString().substring(0, 80)));
  console.log("[DEBUG] METHOD 1 — rangeCount:", selAfter.rangeCount);
  if (selAfter.rangeCount > 0) {
    console.log("[DEBUG] METHOD 1 — selection collapsed:", selAfter.getRangeAt(0).collapsed);
  }
  console.log("[DEBUG] METHOD 1 — innerHTML (first 500):", JSON.stringify(contentEditable.innerHTML.substring(0, 500)));

  await new Promise(r => setTimeout(r, 400));

  // [DEBUG] After Method 1 wait
  console.log("[DEBUG] AFTER M1 WAIT — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));
  console.log("[DEBUG] AFTER M1 WAIT — innerHTML (first 500):", JSON.stringify(contentEditable.innerHTML.substring(0, 500)));
  console.log("[DEBUG] AFTER M1 WAIT — document.activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : null);

  if (contentEditable.textContent.trim().length > 0) {
    console.log("[ContentScript] Method 1 (selectAllChildren + insertText) succeeded");
    return true;
  }
  console.log("[ContentScript] Method 1 failed. textContent:", JSON.stringify(contentEditable.textContent.substring(0, 80)));

  // ── Method 2: Paste event with mocked clipboardData ──────────────────────────
  // Draft.js paste handler calls event.clipboardData.getData('text/plain').
  // We mock clipboardData via Object.defineProperty because DataTransfer.getData()
  // always returns "" in Chrome extension content scripts.
  contentEditable.focus();

  // [DEBUG] Before paste
  console.log("[DEBUG] M2 BEFORE PASTE — activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : null);
  console.log("[DEBUG] M2 BEFORE PASTE — activeElement === contentEditable:", document.activeElement === contentEditable);
  console.log("[DEBUG] M2 BEFORE PASTE — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));

  const pasteEvent = new ClipboardEvent('paste', { bubbles: true, cancelable: true });
  Object.defineProperty(pasteEvent, 'clipboardData', {
    value: {
      getData(type) {
        console.log("[DEBUG] M2 PASTE — getData called with type:", type, "returning:", (type === 'text/plain' || type === 'text') ? text.substring(0, 40) : '');
        return (type === 'text/plain' || type === 'text') ? text : '';
      },
      types: ['text/plain'],
      files: [],
      items: [],
    },
  });
  const dispatchResult2 = contentEditable.dispatchEvent(pasteEvent);

  // [DEBUG] After paste
  console.log("[DEBUG] M2 AFTER PASTE — activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : null);
  console.log("[DEBUG] M2 AFTER PASTE — dispatchEvent returned:", dispatchResult2);
  console.log("[DEBUG] M2 AFTER PASTE — clipboardData.getData result:", pasteEvent.clipboardData ? pasteEvent.clipboardData.getData('text/plain') : 'NO clipboardData');
  console.log("[DEBUG] M2 AFTER PASTE — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));
  console.log("[DEBUG] M2 AFTER PASTE — innerHTML (first 500):", JSON.stringify(contentEditable.innerHTML.substring(0, 500)));

  await new Promise(r => setTimeout(r, 400));

  // [DEBUG] After Method 2 wait
  console.log("[DEBUG] AFTER M2 WAIT — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));
  console.log("[DEBUG] AFTER M2 WAIT — innerHTML (first 500):", JSON.stringify(contentEditable.innerHTML.substring(0, 500)));
  console.log("[DEBUG] AFTER M2 WAIT — document.activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : null);

  if (contentEditable.textContent.trim().length > 0) {
    console.log("[ContentScript] Method 2 (paste mock) succeeded");
    return true;
  }
  console.log("[ContentScript] Method 2 failed. textContent:", JSON.stringify(contentEditable.textContent.substring(0, 80)));

  // ── Method 3: InputEvent('beforeinput') ──────────────────────────────────────
  // Newer Draft.js / React 17+ handles beforeinput via the native event bridge.
  contentEditable.focus();

  // [DEBUG] Before beforeinput
  console.log("[DEBUG] M3 BEFORE BEFOREINPUT — activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : null);
  console.log("[DEBUG] M3 BEFORE BEFOREINPUT — activeElement === contentEditable:", document.activeElement === contentEditable);
  console.log("[DEBUG] M3 BEFORE BEFOREINPUT — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));

  const biEvent = new InputEvent('beforeinput', {
    inputType: 'insertText',
    data: text,
    bubbles: true,
    cancelable: true,
  });
  const dispatchResult3 = contentEditable.dispatchEvent(biEvent);

  // [DEBUG] After beforeinput
  console.log("[DEBUG] M3 AFTER BEFOREINPUT — activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : null);
  console.log("[DEBUG] M3 AFTER BEFOREINPUT — dispatchEvent returned:", dispatchResult3);
  console.log("[DEBUG] M3 AFTER BEFOREINPUT — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));
  console.log("[DEBUG] M3 AFTER BEFOREINPUT — innerHTML (first 500):", JSON.stringify(contentEditable.innerHTML.substring(0, 500)));

  await new Promise(r => setTimeout(r, 400));

  // [DEBUG] After Method 3 wait
  console.log("[DEBUG] AFTER M3 WAIT — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));
  console.log("[DEBUG] AFTER M3 WAIT — innerHTML (first 500):", JSON.stringify(contentEditable.innerHTML.substring(0, 500)));
  console.log("[DEBUG] AFTER M3 WAIT — document.activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') : null);

  if (contentEditable.textContent.trim().length > 0) {
    console.log("[ContentScript] Method 3 (beforeinput) succeeded");
    return true;
  }
  console.log("[ContentScript] Method 3 failed. textContent:", JSON.stringify(contentEditable.textContent.substring(0, 80)));

  // ── [DEBUG] Final state dump ────────────────────────────────────────────────
  console.log("[DEBUG] ===== FINAL STATE DUMP =====");
  console.log("[DEBUG] FINAL — tagName:", contentEditable.tagName);
  console.log("[DEBUG] FINAL — id:", contentEditable.id);
  console.log("[DEBUG] FINAL — className:", contentEditable.className);
  console.log("[DEBUG] FINAL — isContentEditable:", contentEditable.isContentEditable);
  console.log("[DEBUG] FINAL — contentEditable attr:", contentEditable.getAttribute('contenteditable'));
  console.log("[DEBUG] FINAL — innerHTML (first 500):", JSON.stringify(contentEditable.innerHTML.substring(0, 500)));
  console.log("[DEBUG] FINAL — textContent:", JSON.stringify(contentEditable.textContent.substring(0, 120)));
  console.log("[DEBUG] FINAL — childNodes.length:", contentEditable.childNodes.length);
  for (let i = 0; i < contentEditable.childNodes.length; i++) {
    const cn = contentEditable.childNodes[i];
    console.log("[DEBUG] FINAL — child[" + i + "]: nodeName=" + cn.nodeName + " nodeType=" + cn.nodeType + " textContent=" + JSON.stringify((cn.textContent || '').substring(0, 60)));
  }
  console.log("[DEBUG] FINAL — document.activeElement:", document.activeElement ? document.activeElement.tagName + (document.activeElement.id ? '#' + document.activeElement.id : '') + (document.activeElement.className ? '.' + document.activeElement.className.substring(0, 40) : '') : null);
  console.log("[DEBUG] FINAL — activeElement === contentEditable:", document.activeElement === contentEditable);

  // Check React keys on contentEditable one more time at the end
  const finalKeys = Object.keys(contentEditable).filter(k => k.startsWith('__react'));
  console.log("[DEBUG] FINAL — React keys on contentEditable:", finalKeys.length > 0 ? finalKeys : 'NONE');
  // Check all data-* and aria-* attributes
  const allAttrs = [];
  for (let i = 0; i < contentEditable.attributes.length; i++) {
    allAttrs.push(contentEditable.attributes[i].name + '="' + contentEditable.attributes[i].value + '"');
  }
  console.log("[DEBUG] FINAL — all attributes:", allAttrs.join(', '));

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

    // Click to ensure the Draft.js editor is initialised
    descContainer.click();
    await new Promise(r => setTimeout(r, 500));

    // Locate the contenteditable Draft.js manages
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
      "class:", contentEditable.className?.substring(0, 60));

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
    });
    sendResponse({ status: "success" });
  }
});

console.log("[ContentScript] Pinterest Pre-filler content script loaded.");