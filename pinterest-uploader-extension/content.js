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
  contentEditable.scrollIntoView({ behavior: 'instant', block: 'nearest' });
  await new Promise(r => setTimeout(r, 100));

  // ── Method 1: selectAllChildren (scoped) + execCommand('insertText') ──────────
  // focus() and selection must be set synchronously — no await in between —
  // so Pinterest's React code cannot steal focus before execCommand fires.
  contentEditable.focus();
  window.getSelection().selectAllChildren(contentEditable);
  const m1Result = document.execCommand('insertText', false, text);
  console.log("[ContentScript] Method 1 execCommand('insertText') returned:", m1Result);
  await new Promise(r => setTimeout(r, 400));

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
  const pasteEvent = new ClipboardEvent('paste', { bubbles: true, cancelable: true });
  Object.defineProperty(pasteEvent, 'clipboardData', {
    value: {
      getData(type) {
        return (type === 'text/plain' || type === 'text') ? text : '';
      },
      types: ['text/plain'],
      files: [],
      items: [],
    },
  });
  contentEditable.dispatchEvent(pasteEvent);
  await new Promise(r => setTimeout(r, 400));

  if (contentEditable.textContent.trim().length > 0) {
    console.log("[ContentScript] Method 2 (paste mock) succeeded");
    return true;
  }
  console.log("[ContentScript] Method 2 failed. textContent:", JSON.stringify(contentEditable.textContent.substring(0, 80)));

  // ── Method 3: InputEvent('beforeinput') ──────────────────────────────────────
  // Newer Draft.js / React 17+ handles beforeinput via the native event bridge.
  contentEditable.focus();
  contentEditable.dispatchEvent(new InputEvent('beforeinput', {
    inputType: 'insertText',
    data: text,
    bubbles: true,
    cancelable: true,
  }));
  await new Promise(r => setTimeout(r, 400));

  if (contentEditable.textContent.trim().length > 0) {
    console.log("[ContentScript] Method 3 (beforeinput) succeeded");
    return true;
  }
  console.log("[ContentScript] Method 3 failed. textContent:", JSON.stringify(contentEditable.textContent.substring(0, 80)));

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