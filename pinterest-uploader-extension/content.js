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

    // Click the container to activate the editor
    descContainer.click();
    descContainer.dispatchEvent(new Event('focusin', { bubbles: true }));
    descContainer.dispatchEvent(new Event('focus', { bubbles: true }));
    await new Promise(r => setTimeout(r, 1500));

    // Find the contenteditable element — Draft.js creates it lazily,
    // so first try multiple selectors synchronously, then fall back to waitForElement.
    let contentEditable = descContainer.querySelector(
      '[contenteditable="true"], ' +
      '.public-DraftEditor-content, ' +
      '[aria-label*="опис" i], ' +
      '[aria-label*="description" i]'
    );

    if (!contentEditable) {
      // Draft.js may not have rendered the contenteditable yet.
      // Wait for it using the known aria-label from the DOM dump.
      try {
        contentEditable = await waitForElement(
          '#dweb-comment-editor-container [contenteditable="true"], ' +
          '#dweb-comment-editor-container .public-DraftEditor-content, ' +
          '#dweb-comment-editor-container [aria-label*="опис" i], ' +
          '#dweb-comment-editor-container [aria-label*="description" i]',
          10000
        );
      } catch (e) {
        console.log("[ContentScript] contenteditable not found via waitForElement either");
      }
    }

    console.log("[ContentScript] contentEditable found:", !!contentEditable);

    if (contentEditable) {
      // Focus the editor
      contentEditable.focus();
      contentEditable.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      contentEditable.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
      await new Promise(r => setTimeout(r, 200));

      // Draft.js renders text inside <span data-text="true"> elements
      // inside a structure: div[data-contents="true"] > div[data-block="true"] > div > span > span[data-text="true"]
      //
      // Approach: Find or create the data-text span and set its textContent,
      // then dispatch events on the contentEditable element.

      // Get or create the data-contents container
      let dataContents = contentEditable.querySelector('div[data-contents="true"]');
      if (!dataContents) {
        dataContents = document.createElement('div');
        dataContents.setAttribute('data-contents', 'true');
        contentEditable.appendChild(dataContents);
      }

      // Get or create the data-block div
      let dataBlock = dataContents.querySelector('div[data-block="true"]');
      if (!dataBlock) {
        dataBlock = document.createElement('div');
        dataBlock.setAttribute('data-block', 'true');
        dataBlock.setAttribute('data-editor', Math.random().toString(36).substring(2, 7));
        dataBlock.setAttribute('data-offset-key', Math.random().toString(36).substring(2, 10) + '-0-0');
        dataContents.appendChild(dataBlock);
      }

      // Get or create the block style div
      let blockStyleDiv = dataBlock.querySelector('.public-DraftStyleDefault-block');
      if (!blockStyleDiv) {
        blockStyleDiv = document.createElement('div');
        blockStyleDiv.className = 'public-DraftStyleDefault-block public-DraftStyleDefault-ltr';
        dataBlock.appendChild(blockStyleDiv);
      }

      // Get or create the offset-key span
      let offsetSpan = blockStyleDiv.querySelector('span[data-offset-key]');
      if (!offsetSpan) {
        offsetSpan = document.createElement('span');
        offsetSpan.setAttribute('data-offset-key', Math.random().toString(36).substring(2, 10) + '-0-0');
        blockStyleDiv.appendChild(offsetSpan);
      }

      // Get or create the data-text span — THIS is where Draft.js reads text from
      let dataTextSpan = offsetSpan.querySelector('span[data-text="true"]');
      if (!dataTextSpan) {
        dataTextSpan = document.createElement('span');
        dataTextSpan.setAttribute('data-text', 'true');
        offsetSpan.appendChild(dataTextSpan);
      }

      // Set the text content on the data-text span
      dataTextSpan.textContent = data.description;
      console.log("[ContentScript] Set data-text span content to:", data.description.substring(0, 50));

      // Now dispatch events on the contentEditable to trigger Draft.js onChange
      // Draft.js listens for 'input' events on the contentEditable element
      
      // Dispatch input event with inputType
      const inputEvent = new InputEvent('input', {
        bubbles: true,
        cancelable: true,
        inputType: 'insertText',
        data: data.description,
      });
      contentEditable.dispatchEvent(inputEvent);
      console.log("[ContentScript] Input event dispatched on contentEditable");

      // Also dispatch a change event
      contentEditable.dispatchEvent(new Event('change', { bubbles: true }));

      // Force React to re-render by dispatching a custom DOM event
      // Some Draft.js versions also check for 'compositionend' or 'paste'
      const pasteEvent = new ClipboardEvent('paste', {
        bubbles: true,
        cancelable: true,
      });
      Object.defineProperty(pasteEvent, 'clipboardData', {
        value: {
          getData: () => data.description,
          types: ['text/plain'],
        },
      });
      contentEditable.dispatchEvent(pasteEvent);
      console.log("[ContentScript] Paste event dispatched");

      results.description = "ok";
      console.log("[ContentScript] Description set successfully via data-text span manipulation");
    } else {
      throw new Error("Could not find public-DraftEditor-content element");
    }
  } catch (err) {
    results.description = "error: " + err.message;
    console.warn("[ContentScript] Failed to set description:", err.message);
  }

  // 3. Set Destination URL
  try {
    // Try multiple selectors for the URL/link input
    let urlInput = null;

    // Strategy 1: Try all the specific selectors
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

    // Strategy 2: Broader search — find any visible input/textarea that isn't the title or search
    if (!urlInput) {
      const allInputs = document.querySelectorAll('input, textarea');
      for (const el of allInputs) {
        if (el.id === 'storyboard-selector-title') continue; // skip title
        if (el.type === 'hidden') continue;
        if (el.type === 'file') continue;
        if (el.type === 'checkbox') continue;
        if (el.type === 'radio') continue;
        // Skip search inputs
        if (el.id.toLowerCase().includes('search')) continue;
        if ((el.placeholder || '').toLowerCase().includes('search')) continue;
        if ((el.name || '').toLowerCase().includes('search')) continue;
        // Check if it's visible
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