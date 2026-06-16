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

    // Try clicking the container first to activate the editor
    descContainer.click();
    await new Promise(r => setTimeout(r, 500));

    // Search for ANY element with contenteditable attribute (span, div, etc.)
    let descInput = descContainer.querySelector('[contenteditable]');
    console.log("[ContentScript] contenteditable element found:", !!descInput);

    if (!descInput) {
      // Try the DraftEditor-editorContainer approach
      const editorContainer = descContainer.querySelector('.DraftEditor-editorContainer');
      console.log("[ContentScript] DraftEditor-editorContainer found:", !!editorContainer);
      
      if (editorContainer) {
        // Find the deepest child element (the actual text span)
        const allElements = editorContainer.querySelectorAll('*');
        console.log("[ContentScript] Elements inside editorContainer:", allElements.length);
        
        let deepest = null;
        let maxDepth = 0;
        for (const el of allElements) {
          let depth = 0;
          let parent = el.parentElement;
          while (parent && parent !== editorContainer) {
            depth++;
            parent = parent.parentElement;
          }
          if (depth > maxDepth) {
            maxDepth = depth;
            deepest = el;
          }
        }
        console.log("[ContentScript] Deepest element:", deepest?.tagName, deepest?.className);
        descInput = deepest;
      }
    }

    if (descInput) {
      descInput.focus();
      // Clear existing content first
      descInput.textContent = '';
      // Use execCommand to insert text (works with Draft.js)
      document.execCommand('insertText', false, data.description);
      results.description = "ok";
      console.log("[ContentScript] Description set successfully");
    } else {
      throw new Error("Could not find any editable element inside description container");
    }
  } catch (err) {
    results.description = "error: " + err.message;
    console.warn("[ContentScript] Failed to set description:", err.message);
  }

  // 3. Set Destination URL
  try {
    // Try multiple selectors for the URL/link input
    const urlInput = await waitForElement(
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
    simulateInput(urlInput, data.url);
    results.url = "ok";
    console.log("[ContentScript] URL set successfully");
  } catch (err) {
    results.url = "error: " + err.message;
    console.warn("[ContentScript] Failed to set URL:", err.message);
  }

  // 4. Upload Image
  if (data.imageBase64) {
    try {
      // Wait a bit for the file input to be ready
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
    // Execute asynchronously but respond immediately
    prefillPinData(request.data).then((results) => {
      console.log("[ContentScript] Prefill completed:", results);
    });
    sendResponse({ status: "success" });
  }
});

console.log("[ContentScript] Pinterest Pre-filler content script loaded.");